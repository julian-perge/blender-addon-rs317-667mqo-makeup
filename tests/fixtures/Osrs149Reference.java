import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import java.lang.reflect.Array;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HexFormat;
import net.runelite.cache.definitions.ModelDefinition;
import net.runelite.cache.definitions.loaders.ModelLoader;

/** Records source fields before renderer normalization, alongside the unchanged revision-149 client. */
public final class Osrs149Reference {
    private static final Gson JSON = new GsonBuilder().serializeNulls().create();

    public static void main(String[] args) throws Exception {
        Path input = null, output = null, client = null;
        for (int i = 0; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing argument value");
            switch (args[i]) {
                case "--input" -> input = Path.of(args[i + 1]);
                case "--output" -> output = Path.of(args[i + 1]);
                case "--client" -> client = Path.of(args[i + 1]);
                default -> throw new IllegalArgumentException("Unknown argument: " + args[i]);
            }
        }
        if (input == null || output == null || client == null) {
            throw new IllegalArgumentException("Required: --input <DAT directory> --output <new JSON directory> --client <149.jar>");
        }
        String clientHash = hash(Files.readAllBytes(client));
        if (!clientHash.equals("19c492cc2dc20e9fcb0399215fc32a47cd4605b01a30d963dac7a0c863ebcbdd")) {
            throw new IllegalArgumentException("Unrecognized revision-149 reference artifact");
        }
        Files.createDirectories(output);
        try (URLClassLoader loader = new URLClassLoader(new URL[]{client.toUri().toURL()}, ClassLoader.getPlatformClassLoader());
             var files = Files.list(input)) {
            Class<?> sourceType = Class.forName("dv", true, loader);
            Constructor<?> constructor = sourceType.getDeclaredConstructor(byte[].class);
            constructor.setAccessible(true);
            Method light = sourceType.getDeclaredMethod("ae", int.class, int.class, int.class, int.class, int.class);
            light.setAccessible(true);
            var paths = files.filter(p -> p.toString().endsWith(".dat"))
                .sorted(Comparator.comparingInt(p -> Integer.parseInt(p.getFileName().toString().replace(".dat", "")))).toList();
            for (Path dat : paths) {
                int id = Integer.parseInt(dat.getFileName().toString().replace(".dat", ""));
                Path target = output.resolve(id + ".json");
                if (Files.exists(target)) throw new IllegalArgumentException("Reference already exists: " + target);
                byte[] bytes = Files.readAllBytes(dat);
                ModelDefinition model = new ModelLoader().load(id, bytes);
                boolean newer = bytes.length >= 2 && bytes[bytes.length - 1] == -1 && bytes[bytes.length - 2] == -1;
                JsonObject record = new JsonObject();
                record.addProperty("id", id);
                record.addProperty("encoding", newer ? "osrs-ffff" : "old");
                record.addProperty("source_sha256", hash(bytes));
                record.addProperty("client_sha256", clientHash);
                record.add("vertices", triples(model.vertexX, model.vertexY, model.vertexZ));
                record.add("faces", triples(model.faceIndices1, model.faceIndices2, model.faceIndices3));
                record.add("raw", raw(bytes, newer));
                Object clientModel = constructor.newInstance((Object)bytes);
                record.add("client_raw", fields(clientModel));
                record.add("client_lit", fields(light.invoke(clientModel, 64, 768, -50, -10, -50)));
                Files.writeString(target, JSON.toJson(record) + "\n");
            }
            System.out.println("Recorded " + paths.size() + " models through RuneLite and the unchanged revision-149 client");
        }
    }

    // Section offsets follow the pinned RuneLite1.13.6 ModelLoader source, recorded in the fixture README.
    private static JsonObject raw(byte[] data, boolean newer) {
        ByteBuffer footer = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
        int footerAt = data.length - (newer ? 23 : 18);
        footer.position(footerAt);
        int vertices = footer.getShort() & 65535, faces = footer.getShort() & 65535, textures = footer.get() & 255;
        int render = footer.get() & 255, priority = footer.get() & 255, alpha = footer.get() & 255;
        int faceSkin = footer.get() & 255, hasTextures = newer ? footer.get() & 255 : 0, vertexSkin = footer.get() & 255;
        int x = footer.getShort() & 65535, y = footer.getShort() & 65535, z = footer.getShort() & 65535;
        int indexLength = footer.getShort() & 65535, coordLength = newer ? footer.getShort() & 65535 : 0;
        int[] kinds = newer ? unsigned(data, 0, textures) : new int[textures];
        int at = newer ? textures + vertices : vertices + faces;
        int renderAt = -1, priorityAt = -1, faceSkinAt = -1, vertexSkinAt = -1, alphaAt = -1;
        if (newer && render == 1) { renderAt = at; at += faces; }
        if (newer) at += faces;
        if (priority == 255) { priorityAt = at; at += faces; }
        if (faceSkin == 1) { faceSkinAt = at; at += faces; }
        if (!newer && render == 1) { renderAt = at; at += faces; }
        if (vertexSkin == 1) { vertexSkinAt = at; at += vertices; }
        if (alpha == 1) { alphaAt = at; at += faces; }
        at += indexLength;
        int[] textureIds = new int[faces]; Arrays.fill(textureIds, -1);
        if (newer && hasTextures == 1) {
            textureIds = shorts(data, at, faces);
            for (int i = 0; i < faces; i++) textureIds[i]--;
            at += faces * 2;
        }
        int coordsAt = at;
        if (newer) at += coordLength;
        int[] colours = shorts(data, at, faces); at += faces * 2;
        int[] renderTypes = renderAt < 0 ? new int[faces] : unsigned(data, renderAt, faces);
        int[] coordinateIds = new int[faces]; Arrays.fill(coordinateIds, -1);
        if (newer) {
            int used = 0;
            if (textures > 0) for (int i = 0; i < faces; i++) {
                if (textureIds[i] != -1) coordinateIds[i] = (data[coordsAt + used++] & 255) - 1;
            }
            if (used != coordLength) throw new IllegalArgumentException("Coordinate stream length mismatch");
        } else {
            for (int i = 0; i < faces; i++) {
                int info = renderTypes[i];
                if ((info & 2) != 0) { textureIds[i] = colours[i]; coordinateIds[i] = info >> 2; }
                renderTypes[i] = info & 1;
            }
        }
        int simple = 0, complex = 0, typeTwo = 0;
        for (int kind : kinds) {
            if (kind == 0) simple++;
            else if (kind >= 1 && kind <= 3) complex++;
            else throw new IllegalArgumentException("Unsupported texture record type");
            if (kind == 2) typeTwo++;
        }
        int simpleAt, complexAt, scaleAt, rotationAt, directionAt, speedAt, tailAt;
        if (newer) {
            simpleAt = at + x + y + z;
            complexAt = simpleAt + simple * 6;
            scaleAt = complexAt + complex * 6;
            rotationAt = scaleAt + complex * 6;
            directionAt = rotationAt + complex * 2;
            speedAt = directionAt + complex;
            tailAt = speedAt + complex * 2 + typeTwo * 2;
        } else {
            simpleAt = at; complexAt = scaleAt = rotationAt = directionAt = speedAt = 0;
            tailAt = at + textures * 6 + x + y + z;
        }
        JsonArray records = new JsonArray();
        for (int kind : kinds) {
            JsonObject record = new JsonObject(); record.addProperty("kind", kind);
            if (kind == 0) {
                record.add("words", JSON.toJsonTree(shorts(data, simpleAt, 3))); simpleAt += 6;
                record.addProperty("parameters_hex", "");
            } else {
                record.add("words", JSON.toJsonTree(shorts(data, complexAt, 3))); complexAt += 6;
                var extra = new java.io.ByteArrayOutputStream();
                extra.write(data, scaleAt, 6); scaleAt += 6;
                extra.write(data, rotationAt, 2); rotationAt += 2;
                extra.write(data, directionAt++, 1);
                int speedLength = kind == 2 ? 4 : 2;
                extra.write(data, speedAt, speedLength); speedAt += speedLength;
                record.addProperty("parameters_hex", HexFormat.of().formatHex(extra.toByteArray()));
            }
            records.add(record);
        }
        if (tailAt > footerAt) throw new IllegalArgumentException("Sections overlap footer");
        JsonObject raw = new JsonObject();
        raw.add("section_flags", JSON.toJsonTree(newer ? new int[]{render,priority,alpha,faceSkin,hasTextures,vertexSkin} : new int[]{render,priority,alpha,faceSkin,vertexSkin}));
        raw.add("face_colours", JSON.toJsonTree(colours)); raw.add("face_textures", JSON.toJsonTree(textureIds));
        raw.add("face_texture_indices", JSON.toJsonTree(coordinateIds)); raw.add("face_render_types", JSON.toJsonTree(renderTypes));
        int[] priorities = priorityAt >= 0 ? unsigned(data, priorityAt, faces) : new int[faces];
        if (priorityAt < 0) Arrays.fill(priorities, priority);
        raw.add("render_priorities", JSON.toJsonTree(priorities));
        raw.add("face_alphas", JSON.toJsonTree(alphaAt >= 0 ? unsigned(data, alphaAt, faces) : new int[faces]));
        raw.add("face_skins", faceSkinAt >= 0 ? JSON.toJsonTree(unsigned(data, faceSkinAt, faces)) : JsonNull.INSTANCE);
        raw.add("vertex_skins", vertexSkinAt >= 0 ? JSON.toJsonTree(unsigned(data, vertexSkinAt, vertices)) : JsonNull.INSTANCE);
        raw.add("texture_records", records);
        raw.addProperty("tail_hex", HexFormat.of().formatHex(Arrays.copyOfRange(data, tailAt, footerAt)));
        return raw;
    }

    private static JsonObject fields(Object value) throws Exception {
        JsonObject result = new JsonObject();
        Field[] fields = value.getClass().getDeclaredFields();
        Arrays.sort(fields, Comparator.comparing(Field::getName));
        for (Field field : fields) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            field.setAccessible(true); Object item = field.get(value);
            result.add(field.getName(), primitive(item));
        }
        return result;
    }

    private static JsonElement primitive(Object value) {
        if (value == null) return JsonNull.INSTANCE;
        if (value.getClass().isArray()) {
            JsonArray result = new JsonArray();
            for (int i = 0; i < Array.getLength(value); i++) result.add(primitive(Array.get(value, i)));
            return result;
        }
        if (value instanceof Number || value instanceof Boolean || value instanceof Character) return JSON.toJsonTree(value);
        throw new IllegalArgumentException("Unexpected initialized client field: " + value.getClass());
    }

    private static JsonArray triples(int[] a, int[] b, int[] c) {
        JsonArray result = new JsonArray();
        for (int i = 0; i < a.length; i++) result.add(JSON.toJsonTree(new int[]{a[i], b[i], c[i]}));
        return result;
    }

    private static int[] unsigned(byte[] data, int at, int count) {
        int[] result = new int[count];
        for (int i = 0; i < count; i++) result[i] = data[at + i] & 255;
        return result;
    }

    private static int[] shorts(byte[] data, int at, int count) {
        int[] result = new int[count]; ByteBuffer input = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);input.position(at);
        for (int i = 0; i < count; i++) result[i] = input.getShort() & 65535;
        return result;
    }

    private static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
