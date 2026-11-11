import java.lang.reflect.Array;
import java.lang.reflect.Modifier;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Captures the unchanged hu.l pipeline at entry to dv.ae using a JVMTI method-entry observer. */
public final class AppearanceReference {
    static final int[] EQUIPMENT = {0,0,0,0,274,0,282,292,256,289,298,266};
    static final int[] FEMALE_EQUIPMENT = {0,0,0,0,312,0,317,326,301,323,335,0};
    static final int[][] COLOURS = {{0,0,0,0,0}, {1,2,3,4,5}};

    static final int[] ITEMS = {1149,2653,3140,4087,35};
    static final List<Integer> ITEM_MERGES = new ArrayList<>();

    public static void captureMerge(int count) { ITEM_MERGES.add(count); }

    static final List<String> CAPTURES = new ArrayList<>();

    public static void main(String[] args) throws Exception {
        worker(args);
        if (CAPTURES.size() != 16) throw new IllegalStateException("Expected sixteen lighting entries");
        Files.writeString(Path.of(args[4], "raw.json"), "[" + String.join(",", CAPTURES) + "]\n");
    }

    public static void capture(Object model) throws Exception {
        CAPTURES.add(json(snapshot(model)));
    }

    static String quote(String text) { return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\""; }

    static void worker(String[] args) throws Exception {
        Path models = Path.of(args[2]), kits = Path.of(args[3]), output = Path.of(args[4]);
        try (var loader = new URLClassLoader(new URL[]{Path.of(args[1]).toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            Class<?> archive = loader.loadClass("if"), kit = loader.loadClass("it"), appearance = loader.loadClass("hu");
            Object modelArchive = emptyArchive(loader), kitArchive = emptyArchive(loader);
            List<Path> modelPaths;
            try (var paths = Files.list(models)) {
                modelPaths = paths.filter(p -> p.toString().endsWith(".dat")).toList();
            }
            int highestModel = modelPaths.stream().mapToInt(p -> Integer.parseInt(p.getFileName().toString().replace(".dat", ""))).max().orElseThrow();
            Object[][] modelFiles = new Object[highestModel + 1][];
            try (var paths = Files.list(models)) {
                for (Path path : paths.filter(p -> p.toString().endsWith(".dat")).toList()) {
                    int id = Integer.parseInt(path.getFileName().toString().replace(".dat", ""));
                    modelFiles[id] = new Object[]{Files.readAllBytes(path)};
                }
            }
            field(archive, "u").set(modelArchive, modelFiles);
            Object[][] kitFiles = new Object[4][];
            kitFiles[3] = new Object[151];
            for (int id = 0; id < 151; id++) kitFiles[3][id] = Files.readAllBytes(kits.resolve(id + ".dat"));
            field(archive, "u").set(kitArchive, kitFiles);
            kit.getDeclaredMethod("w", archive, archive).invoke(null, kitArchive, modelArchive);
            Class<?> item = loader.loadClass("iz");
            Object itemArchive = emptyArchive(loader);
            Object[][] itemFiles = new Object[11][];
            itemFiles[10] = new Object[Arrays.stream(ITEMS).max().orElseThrow() + 1];
            for (int id : ITEMS) itemFiles[10][id] = Files.readAllBytes(models.resolve("items").resolve(id + ".dat"));
            field(archive, "u").set(itemArchive, itemFiles);
            field(loader.loadClass("eb"), "e").set(null, itemArchive);
            field(item, "l").set(null, modelArchive);
            Map<String,Object> decodedItems = new TreeMap<>();
            for (int id : ITEMS) {
                Object definition = loader.loadClass("cu").getDeclaredMethod("j", int.class, int.class).invoke(null, id, -1827004326);
                Map<String,Object> decoded = new TreeMap<>();
                decoded.put("client_raw", snapshot(definition));
                decoded.put("recolours", pairs(definition, "o", "x"));
                decoded.put("retextures", pairs(definition, "f", "h"));
                  for (boolean female : new boolean[]{false, true}) {
                        Map<String,Object> body = new TreeMap<>();
                        body.put("model_ids", female
                            ? new int[]{logical(definition,"ag",-342824299), logical(definition,"aj",1991139359), logical(definition,"az",85456167)}
                            : new int[]{logical(definition,"aw",-1032210027), logical(definition,"aq",-1410308759), logical(definition,"ad",-2049145749)});
                        body.put("offset", female ? logical(definition,"ax",-761981003) : logical(definition,"aa",-1445417827));
                        ITEM_MERGES.clear();
                        Object worn = item.getDeclaredMethod("k", boolean.class, byte.class).invoke(definition, female, (byte)-54);
                        body.put("merge_counts", new ArrayList<>(ITEM_MERGES));
                        body.put("before_player_merge", worn == null ? null : Map.of(
                            "vertex_count", field(worn.getClass(),"a").get(worn), "face_count", field(worn.getClass(),"v").get(worn)));
                        decoded.put(female ? "female" : "male", body);
                    }
                    decodedItems.put(Integer.toString(id), decoded);
                }
                Files.writeString(output.resolve("items.json"), json(decodedItems) + "\n");
                Class<?> hv = Class.forName("hv", true, loader);
                field(appearance, "l").set(null, field(hv, "a").get(null));
                field(appearance, "w").set(null, field(hv, "n").get(null));
                field(loader.loadClass("gw"), "s").set(null, field(hv, "j").get(null));
                field(loader.loadClass("cd"), "p").set(null, field(hv, "r").get(null));
                Map<String,Object> palette = new TreeMap<>();
                for (String name : List.of("a", "j", "n", "r")) palette.put(name, field(hv, name).get(null));
                Files.writeString(output.resolve("palette.json"), json(palette) + "\n");
                List<Object> decodedKits = new ArrayList<>();
                var getKit = kit.getDeclaredMethod("m", int.class);
                getKit.setAccessible(true);
                for (int id = 0; id < 151; id++) decodedKits.add(snapshot(getKit.invoke(null, id)));
                Files.writeString(output.resolve("kits.json"), json(decodedKits) + "\n");
                Map<String,Object> defaults = new TreeMap<>();
                for (boolean female : new boolean[]{false, true}) {
                    Object player = appearance.getDeclaredConstructor().newInstance();
                    appearance.getDeclaredMethod("a", int[].class, int[].class, boolean.class, int.class, int.class)
                        .invoke(player, null, COLOURS[0].clone(), female, -1, -2032808093);
                    defaults.put(female ? "female" : "male", field(appearance, "a").get(player));
                }
                Files.writeString(output.resolve("defaults.json"), json(defaults) + "\n");
                List<Object> lit = new ArrayList<>();
                List<Object> settings = new ArrayList<>();
                for (String outfit : new String[]{null, "dragon_plate", "dragon_chain", "excalibur"}) {
                  for (boolean female : new boolean[]{false, true}) {
                    for (int[] colours : COLOURS) {
                        int[] equipment = (female ? FEMALE_EQUIPMENT : EQUIPMENT).clone();
                        if (outfit != null && outfit.equals("excalibur")) {
                            equipment[3] = 512 + 35;
                        } else if (outfit != null) {
                            equipment[0] = 512 + 1149;
                            equipment[4] = 512 + (outfit.equals("dragon_plate") ? 2653 : 3140);
                            equipment[7] = 512 + 4087;
                        }
                        Map<String,Object> setting = new LinkedHashMap<>();
                        setting.put("female", female);
                        setting.put("colours", colours);
                        setting.put("equipment", equipment);
                        if (outfit != null) setting.put("outfit", outfit);
                        settings.add(setting);
                        Object player = appearance.getDeclaredConstructor().newInstance();
                        appearance.getDeclaredMethod("a", int[].class, int[].class, boolean.class, int.class, int.class)
                            .invoke(player, equipment, colours, female, -1, 0);
                        Object model = appearance.getDeclaredMethod("l", loader.loadClass("jg"), int.class,
                            loader.loadClass("jg"), int.class, byte.class).invoke(player, null, 0, null, 0, (byte)127);
                        if (model == null) throw new IllegalStateException("Client returned no model");
                        lit.add(snapshot(model));
                    }
                }
            }
            Files.writeString(output.resolve("settings.json"), json(settings) + "\n");
            Files.writeString(output.resolve("lit.json"), json(lit) + "\n");
        }
    }

    // Only archive storage is supplied; no archive constructor, disk cache, network or game startup runs.
    static Object emptyArchive(ClassLoader loader) throws Exception {
        Class<?> unsafe = Class.forName("sun.misc.Unsafe");
        Object allocator = field(unsafe, "theUnsafe").get(null);
        return unsafe.getMethod("allocateInstance", Class.class).invoke(allocator, loader.loadClass("ig"));
    }

    static int logical(Object item, String name, int multiplier) throws Exception {
        return field(item.getClass(), name).getInt(item) * multiplier;
    }

    static List<Object> pairs(Object item, String from, String to) throws Exception {
        short[] sources = (short[]) field(item.getClass(), from).get(item);
        short[] targets = (short[]) field(item.getClass(), to).get(item);
        List<Object> result = new ArrayList<>();
        if (sources != null) for (int i = 0; i < sources.length; i++) result.add(new int[]{sources[i] & 65535, targets[i] & 65535});
        return result;
    }

    static java.lang.reflect.Field field(Class<?> type, String name) throws Exception {
        var field = type.getDeclaredField(name); field.setAccessible(true); return field;
    }

    static Map<String,Object> snapshot(Object value) throws Exception {
        Map<String,Object> result = new TreeMap<>();
        for (var field : value.getClass().getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            field.setAccessible(true); result.put(field.getName(), field.get(value));
        }
        return result;
    }

    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) return quote(text);
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?,?> map) {
            StringJoiner result = new StringJoiner(",", "{", "}");
            map.forEach((key, item) -> result.add(quote(key.toString()) + ":" + json(item)));
            return result.toString();
        }
        if (value instanceof Iterable<?> items) {
            StringJoiner result = new StringJoiner(",", "[", "]");
            items.forEach(item -> result.add(json(item))); return result.toString();
        }
        if (value.getClass().isArray()) {
            List<Object> items = new ArrayList<>();
            for (int i = 0; i < Array.getLength(value); i++) items.add(Array.get(value, i));
            return json(items);
        }
        throw new IllegalArgumentException("Unexpected client field: " + value.getClass());
    }
}
