import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.awt.image.BufferedImage;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.imageio.ImageIO;
import net.runelite.cache.definitions.ItemDefinition;
import net.runelite.cache.definitions.TextureDefinition;
import net.runelite.cache.definitions.loaders.ItemLoader;
import net.runelite.cache.definitions.loaders.ModelLoader;
import net.runelite.cache.definitions.loaders.SpriteLoader;
import net.runelite.cache.definitions.loaders.TextureLoader;
import net.runelite.cache.definitions.providers.ItemProvider;
import net.runelite.cache.definitions.providers.ModelProvider;
import net.runelite.cache.definitions.providers.SpriteProvider;
import net.runelite.cache.definitions.providers.TextureProvider;
import net.runelite.cache.fs.Archive;
import net.runelite.cache.fs.Store;
import net.runelite.cache.item.ItemSpriteFactory;
import net.runelite.cache.item.GuardedItemSpriteFactory;

/** Captures and replays only resources requested by three real inventory icons. */
public final class Osrs149IconReference {
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private final Path output;
    private final Path closure;
    private final Store cache;

    private Osrs149IconReference(Path input, Path output, boolean capture) throws Exception {
        this.output = output;
        this.closure = capture ? null : input;
        this.cache = capture ? new Store(input.toFile()) : null;
        if (cache != null) cache.load();
    }

    private byte[] raw(int index, int archiveId, int fileId) throws Exception {
        Path relative = Path.of("raw", "" + index, "" + archiveId, fileId + ".dat");
        byte[] bytes;
        if (cache == null) bytes = Files.readAllBytes(closure.resolve(relative));
        else {
            Archive archive = cache.findIndex(index).getArchive(archiveId);
            bytes = archive.getFiles(cache.getStorage().loadArchive(archive)).findFile(fileId).getContents();
        }
        Path destination = output.resolve(relative);
        Files.createDirectories(destination.getParent());
        Files.write(destination, bytes);
        return bytes;
    }

    private void record() throws Exception {
        int[] textureIds;
        if (cache == null) textureIds = JSON.fromJson(Files.readString(closure.resolve("texture-ids.json")), int[].class);
        else {
            Archive archive = cache.findIndex(9).getArchive(0);
            textureIds = archive.getFiles(cache.getStorage().loadArchive(archive)).getFiles().stream()
                .mapToInt(file -> file.getFileId()).sorted().toArray();
        }
        Files.writeString(output.resolve("texture-ids.json"), JSON.toJson(textureIds) + "\n");
        List<TextureDefinition> textures = new ArrayList<>();
        TextureLoader textureLoader = new TextureLoader().setRev233(false);
        for (int id : textureIds) textures.add(textureLoader.load(id, raw(9, 0, id)));
        ItemProvider items = id -> {
            try {
                ItemDefinition item = new ItemLoader().load(id, raw(2, 10, id));
                if (item.notedTemplate != -1 || item.boughtTemplateId != -1 || item.placeholderTemplateId != -1)
                    throw new IllegalArgumentException("Reference selection requires unlinked items");
                return item;
            } catch (Exception error) { throw new IllegalStateException(error); }
        };
        ModelProvider models = id -> {
            try { return new ModelLoader().load(id, raw(7, id, 0)); }
            catch (Exception error) { throw new IllegalStateException(error); }
        };
        SpriteProvider sprites = (id, frame) -> {
            try { return new SpriteLoader().load(id, raw(8, id, 0))[frame]; }
            catch (Exception error) { throw new IllegalStateException(error); }
        };
        TextureProvider textureProvider = () -> textures.toArray(new TextureDefinition[0]);
        for (int id : new int[]{8283, 4151, 995}) {
            BufferedImage guarded = GuardedItemSpriteFactory.createSprite(items, models, sprites, textureProvider,
                id, 1, 1, 0x302020, false);
            ImageIO.write(guarded, "png", output.resolve(id + ".png").toFile());
            try {
                BufferedImage original = ItemSpriteFactory.createSprite(items, models, sprites, textureProvider,
                    id, 1, 1, 0x302020, false);
                if (id == 8283) throw new AssertionError("Original item 8283 no longer reproduces its failure");
                if (!Arrays.equals(original.getRGB(0, 0, 36, 32, null, 0, 36), guarded.getRGB(0, 0, 36, 32, null, 0, 36)))
                    throw new AssertionError("Guard changed successful control icon " + id);
            } catch (ArrayIndexOutOfBoundsException error) {
                if (id != 8283) throw error;
                StringWriter trace = new StringWriter();
                error.printStackTrace(new PrintWriter(trace));
                Files.writeString(output.resolve("8283-original-error.txt"), trace.toString());
            }
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3 || (!args[0].equals("--cache") && !args[0].equals("--closure")))
            throw new IllegalArgumentException("Usage: --cache|--closure <input> <new output>");
        Path output = Path.of(args[2]);
        Files.createDirectory(output);
        Osrs149IconReference recorder = new Osrs149IconReference(Path.of(args[1]), output, args[0].equals("--cache"));
        try { recorder.record(); }
        finally { if (recorder.cache != null) recorder.cache.close(); }
    }
}
