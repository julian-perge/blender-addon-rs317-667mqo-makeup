// Compile beside the unmodified revision-1 client and run with Gson on the classpath.
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class AnimationTransformReference {
    private static int[][] groups(int[] labels) {
        if (labels == null) return null;
        int maximum = Arrays.stream(labels).max().orElse(-1);
        int[][] result = new int[maximum + 1][];
        for (int label = 0; label <= maximum; label++) {
            List<Integer> members = new ArrayList<>();
            for (int i = 0; i < labels.length; i++) if (labels[i] == label) members.add(i);
            result[label] = members.stream().mapToInt(Integer::intValue).toArray();
        }
        return result;
    }

    private static JsonObject capture(String name, int[][] vertices, int[] skins, int[] alphas,
        int[] faceSkins, int[] types, int[][] labels, int[][] transforms) {
        var gson = new GsonBuilder().serializeNulls().create();
        JsonObject result = new JsonObject();
        result.addProperty("name", name);
        result.add("vertices", gson.toJsonTree(vertices));
        result.add("vertex_skins", gson.toJsonTree(skins));
        result.add("face_alphas", gson.toJsonTree(alphas));
        result.add("face_skins", gson.toJsonTree(faceSkins));
        result.add("types", gson.toJsonTree(types));
        result.add("labels", gson.toJsonTree(labels));
        result.add("transforms", gson.toJsonTree(transforms));
        Class104_Sub18_Sub16_Sub4 model = new Class104_Sub18_Sub16_Sub4();
        model.anInt1529 = vertices.length;
        model.anInt1585 = alphas.length;
        model.anIntArray1530 = Arrays.stream(vertices).mapToInt(v -> v[0]).toArray();
        model.anIntArray1531 = Arrays.stream(vertices).mapToInt(v -> v[1]).toArray();
        model.anIntArray1584 = Arrays.stream(vertices).mapToInt(v -> v[2]).toArray();
        model.anIntArrayArray1549 = groups(skins);
        model.anIntArrayArray1550 = groups(faceSkins);
        model.aByteArray1535 = new byte[alphas.length];
        for (int i = 0; i < alphas.length; i++) model.aByteArray1535[i] = (byte) alphas[i];
        Class104_Sub18_Sub16_Sub4.anInt1567 = 0;
        Class104_Sub18_Sub16_Sub4.anInt1576 = 0;
        Class104_Sub18_Sub16_Sub4.anInt1577 = 0;
        for (int[] transform : transforms) {
            int index = transform[0];
            model.method817(types[index], labels[index], transform[1], transform[2], transform[3]);
        }
        int[][] expected = new int[vertices.length][3];
        for (int i = 0; i < expected.length; i++) {
            expected[i] = new int[] {model.anIntArray1530[i], model.anIntArray1531[i], model.anIntArray1584[i]};
        }
        int[] expectedAlphas = new int[alphas.length];
        for (int i = 0; i < alphas.length; i++) expectedAlphas[i] = model.aByteArray1535[i] & 255;
        result.add("expected_vertices", gson.toJsonTree(expected));
        result.add("expected_face_alphas", gson.toJsonTree(expectedAlphas));
        return result;
    }

    public static void main(String[] args) {
        JsonArray cases = new JsonArray();
        int[][] vertices = {{-3, -5, 7}, {4, 1, -2}, {10, -8, 5}};
        int[] skins = {0, 0, 1};
        cases.add(capture("ordered-pivot-duplicate-and-missing-labels", vertices, skins,
            new int[] {0, 240, 255}, new int[] {0, 1, 0}, new int[] {0, 1, 2, 3},
            new int[][] {{0, 0, 99}, {1, 1, 99}, {0, 1}, {0, 1}},
            new int[][] {{0, 1, -2, 3}, {1, 3, -4, 5}, {2, 29, 251, 65}, {3, 64, -129, 257}}));
        cases.add(capture("pivot-reset-and-missing-pivot-label", vertices, skins,
            new int[] {0}, null, new int[] {2, 0, 3}, new int[][] {{0, 1}, {99}, {0, 1}},
            new int[][] {{0, -1, 64, 127}, {1, -7, 11, -13}, {2, -65, 127, 129}}));
        cases.add(capture("signed-int-overflow", new int[][] {{2147483640, -2147483640, 123456789}, {2147483639, -2147483639, -123456789}},
            new int[] {0, 0}, new int[] {128}, new int[] {0}, new int[] {0, 1, 2, 3},
            new int[][] {{0, 0}, {0}, {0}, {0}},
            new int[][] {{0, 2147483647, -2147483648, 0}, {1, 100, -100, 2147483647}, {2, 17, 33, 65}, {3, 2147483647, -2147483648, 129}}));
        cases.add(capture("alpha-clamp-and-repeated-labels", vertices, skins,
            new int[] {0, 240, 255}, new int[] {0, 1, 0}, new int[] {5, 5, 5},
            new int[][] {{0, 0, 99}, {0, 1}, {0, 1}},
            new int[][] {{0, 100, 0, 0}, {1, -100, 0, 0}, {2, 1, 0, 0}}));
        cases.add(capture("alpha-without-face-labels", vertices, skins,
            new int[] {0, 240, 255}, null, new int[] {5}, new int[][] {{0, 99}}, new int[][] {{0, 100, 0, 0}}));
        cases.add(capture("alpha-distinct-groups", vertices, skins,
            new int[] {0, 0, 0}, new int[] {0, 1, 0}, new int[] {5},
            new int[][] {{0}}, new int[][] {{0, 8, 0, 0}}));
        System.out.println(new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(cases));
    }
}
