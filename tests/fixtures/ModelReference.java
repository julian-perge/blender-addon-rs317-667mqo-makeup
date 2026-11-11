import java.nio.file.Files;
import java.nio.file.Path;
import java.util.StringJoiner;
import net.runelite.cache.definitions.ModelDefinition;
import net.runelite.cache.definitions.loaders.ModelLoader;

/**
 * Decodes model files with RuneLite's ModelLoader and writes what it read as JSON next to each file.
 *
 * The tests compare our decoder against these files, so the expected values come from a second,
 * independent implementation of the model formats rather than from our own code.
 *
 * Run with a jar that holds RuneLite's cache library 1.13.6 (net.runelite:cache) and its dependencies:
 * java -cp <path to RuneLite cache jar> tests/fixtures/ModelReference.java tests/fixtures/models/osrs/*.dat
 */
public class ModelReference {
    public static void main(String[] args) throws Exception {
        for (String arg : args) {
            Path dat = Path.of(arg);
            byte[] bytes = Files.readAllBytes(dat);
            ModelDefinition m = new ModelLoader().load(0, bytes);
            StringJoiner json = new StringJoiner(",\n  ", "{\n  ", "\n}\n");
            json.add("\"vertex_x\": " + ints(m.vertexX));
            json.add("\"vertex_y\": " + ints(m.vertexY));
            json.add("\"vertex_z\": " + ints(m.vertexZ));
            json.add("\"face_a\": " + ints(m.faceIndices1));
            json.add("\"face_b\": " + ints(m.faceIndices2));
            json.add("\"face_c\": " + ints(m.faceIndices3));
            json.add("\"face_colours\": " + unsignedShorts(m.faceColors));
            json.add("\"face_render_types\": " + unsignedBytes(m.faceRenderTypes));
            json.add("\"face_render_priorities\": " + unsignedBytes(m.faceRenderPriorities));
            json.add("\"model_priority\": " + (m.priority & 0xff));
            json.add("\"face_alphas\": " + unsignedBytes(m.faceTransparencies));
            json.add("\"face_skins\": " + ints(m.packedTransparencyVertexGroups));
            json.add("\"vertex_skins\": " + ints(vertexSkins(m)));
            json.add("\"face_textures\": " + signedShorts(m.faceTextures));
            json.add("\"face_texture_coords\": " + signedBytes(m.textureCoords));
            json.add("\"texture_p\": " + unsignedShorts(m.texIndices1));
            json.add("\"texture_m\": " + unsignedShorts(m.texIndices2));
            json.add("\"texture_n\": " + unsignedShorts(m.texIndices3));
            json.add("\"texture_render_types\": " + unsignedBytes(m.textureRenderTypes));
            m.computeTextureUVCoordinates();
            json.add("\"face_texture_u\": " + floatRows(m.faceTextureUCoordinates));
            json.add("\"face_texture_v\": " + floatRows(m.faceTextureVCoordinates));
            Path out = dat.resolveSibling(dat.getFileName().toString().replace(".dat", ".json"));
            Files.writeString(out, json.toString());
        }
    }

    // ModelLoader replaces the per-vertex labels with lists of vertex indices per label, so this rebuilds them.
    static int[] vertexSkins(ModelDefinition m) {
        int[][] groups = m.getVertexGroups();
        if (groups == null) return null;
        int[] labels = new int[m.vertexCount];
        for (int label = 0; label < groups.length; label++) {
            for (int vertex : groups[label]) labels[vertex] = label;
        }
        return labels;
    }

    static String ints(int[] a) {
        if (a == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (int v : a) j.add(Integer.toString(v));
        return j.toString();
    }

    // Untextured faces have no row. Java prints a division by zero as NaN or Infinity, which Python's json module reads.
    static String floatRows(float[][] rows) {
        if (rows == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (float[] row : rows) {
            if (row == null) {
                j.add("null");
                continue;
            }
            StringJoiner r = new StringJoiner(", ", "[", "]");
            for (float v : row) r.add(Float.toString(v));
            j.add(r.toString());
        }
        return j.toString();
    }

    static String unsignedBytes(byte[] a) {
        if (a == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (byte v : a) j.add(Integer.toString(v & 0xff));
        return j.toString();
    }

    static String signedBytes(byte[] a) {
        if (a == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (byte v : a) j.add(Integer.toString(v));
        return j.toString();
    }

    static String unsignedShorts(short[] a) {
        if (a == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (short v : a) j.add(Integer.toString(v & 0xffff));
        return j.toString();
    }

    static String signedShorts(short[] a) {
        if (a == null) return "null";
        StringJoiner j = new StringJoiner(", ", "[", "]");
        for (short v : a) j.add(Integer.toString(v));
        return j.toString();
    }
}
