import com.google.gson.JsonObject;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Comparator;
import net.runelite.cache.definitions.loaders.ModelLoader;

/** Compares exported files with original fields through the independently pinned reference reader. */
public final class VerifyOsrs149Roundtrip {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Usage: <original models> <exported models>");
        Method raw = Osrs149Reference.class.getDeclaredMethod("raw", byte[].class, boolean.class);
        raw.setAccessible(true);
        int count = 0;
        try (var files = Files.list(Path.of(args[0]))) {
            for (Path path : files.filter(p -> p.toString().endsWith(".dat"))
                .sorted(Comparator.comparingInt(p -> Integer.parseInt(p.getFileName().toString().replace(".dat", "")))).toList()) {
                byte[] original = Files.readAllBytes(path);
                byte[] exported = Files.readAllBytes(Path.of(args[1]).resolve(path.getFileName()));
                boolean newer = original[original.length - 1] == -1 && original[original.length - 2] == -1;
                boolean outputNewer = exported[exported.length - 1] == -1 && exported[exported.length - 2] == -1;
                if (newer != outputNewer) throw new AssertionError("Encoding changed: " + path);
                JsonObject left = (JsonObject)raw.invoke(null, original, newer);
                JsonObject right = (JsonObject)raw.invoke(null, exported, newer);
                left.remove("section_flags"); right.remove("section_flags");
                if (!left.equals(right)) throw new AssertionError("Raw fields differ: " + path);
                var input = new ModelLoader().load(count, original);
                var output = new ModelLoader().load(count, exported);
                if (!Arrays.equals(input.vertexX, output.vertexX) || !Arrays.equals(input.vertexY, output.vertexY)
                    || !Arrays.equals(input.vertexZ, output.vertexZ) || !Arrays.equals(input.faceIndices1, output.faceIndices1)
                    || !Arrays.equals(input.faceIndices2, output.faceIndices2) || !Arrays.equals(input.faceIndices3, output.faceIndices3))
                    throw new AssertionError("Geometry differs: " + path);
                count++;
            }
        }
        System.out.println("Independently verified geometry and raw source fields for " + count + " exports");
    }
}
