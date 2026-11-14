import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;
import java.util.zip.GZIPOutputStream;
import net.runelite.cache.definitions.SpriteDefinition;
import net.runelite.cache.definitions.TextureDefinition;
import net.runelite.cache.definitions.loaders.SpriteLoader;
import net.runelite.cache.definitions.loaders.TextureLoader;

/**
 * Makes the pixels of textures with RuneLite's TextureDefinition and SpriteLoader and writes them.
 *
 * The tests compare our texture decoder against this file, so the expected values come from a second, independent
 * implementation. It was run with RuneLite's cache library 1.13.6, as ModelReference.java says:
 * java -cp <path to RuneLite cache jar> tests/fixtures/TextureReference.java <texture folder> <sprite folder> <output txt.gz>
 *
 * The texture folder holds one raw texture definition per id, `<id>.dat`, as group 0 of index 9 stores it. The sprite
 * folder holds one sprite group per id, `<id>.dat`, as index 8 stores it after decompression. The loader reads the
 * definitions with `setRev233(false)`, because snapshot 430 stores the layout from before revision 233: a sprite count,
 * the sprite ids, two lists of operations, one colour for each sprite, and the animation direction and speed.
 *
 * For each texture, by id, the file has one line `texture <id> opaque <true or false>`, with the flag that the loader
 * keeps as `field1778`. Then, for each brightness 0.9, 0.8, 0.7 and 0.6, it has one line `brightness <brightness>` and
 * 128 lines of 128 pixels each. Each pixel is the colour 0xRRGGBB that `method2680` gives at size 128, written as 6 hex
 * digits, and the pixels go from the top row to the bottom row and from left to right in a row.
 *
 * `method2680` changes the palette of the sprite that it gets, and RuneLite's SpriteManager keeps one sprite for each id.
 * The provider below decodes the sprite again for each call, as the client does (`Sequence.method5215`), so the
 * brightness of one call does not carry into the next.
 */
public class TextureReference {
    static final double[] BRIGHTNESS = {0.9, 0.8, 0.7, 0.6};

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: <texture folder> <sprite folder> <output txt.gz>");
        }
        Path textures = Path.of(args[0]);
        Path sprites = Path.of(args[1]);
        try (Writer out = new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(Path.of(args[2]))),
                StandardCharsets.US_ASCII)) {
            for (int id : ids(textures)) {
                TextureDefinition texture = new TextureLoader().setRev233(false)
                    .load(id, Files.readAllBytes(textures.resolve(id + ".dat")));
                out.write("texture " + id + " opaque " + texture.field1778 + "\n");
                for (double brightness : BRIGHTNESS) {
                    texture.method2680(brightness, 128, (sprite, frame) -> frame(sprites, sprite, frame));
                    out.write("brightness " + brightness + "\n");
                    for (int row = 0; row < 128; row++) {
                        StringBuilder line = new StringBuilder();
                        for (int column = 0; column < 128; column++) {
                            if (column > 0) line.append(' ');
                            line.append(String.format("%06x", texture.pixels[row * 128 + column]));
                        }
                        out.write(line.append('\n').toString());
                    }
                }
            }
        }
    }

    static SpriteDefinition frame(Path folder, int sprite, int frame) {
        try {
            return new SpriteLoader().load(sprite, Files.readAllBytes(folder.resolve(sprite + ".dat")))[frame];
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    static List<Integer> ids(Path folder) throws Exception {
        try (var paths = Files.list(folder)) {
            return paths.map(p -> p.getFileName().toString()).filter(n -> n.endsWith(".dat"))
                .map(n -> Integer.parseInt(n.substring(0, n.length() - 4))).sorted().collect(Collectors.toList());
        }
    }
}
