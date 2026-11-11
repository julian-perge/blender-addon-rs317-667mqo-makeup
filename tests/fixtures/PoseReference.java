import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Runs the unchanged hu.l with each frame of one clip and records the rest and posed vertices of the lit model. */
public final class PoseReference {
    // args: client jar, appearance fixtures (models), raw kit folder, clip folder, output file, "male" or "female",
    // twelve comma-separated equipment values, five comma-separated colour choices, then optionally a folder of raw
    // item files <id>.dat. With an item folder, the clip's sequence.dat is decoded by the client's own loader du.j, so
    // the sequence carries its held items; without one, the sequence holds only the clip's frame list.
    public static void main(String[] args) throws Exception {
        Path models = Path.of(args[1]), kits = Path.of(args[2]), clip = Path.of(args[3]), output = Path.of(args[4]);
        if (!args[5].equals("male") && !args[5].equals("female")) throw new IllegalArgumentException("Body must be male or female");
        boolean female = args[5].equals("female");
        int[] equipment = Arrays.stream(args[6].split(",")).mapToInt(Integer::parseInt).toArray();
        int[] colours = Arrays.stream(args[7].split(",")).mapToInt(Integer::parseInt).toArray();
        try (var loader = new URLClassLoader(new URL[]{Path.of(args[0]).toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            Class<?> archive = loader.loadClass("if"), kit = loader.loadClass("it"), appearance = loader.loadClass("hu");
            Object modelArchive = AppearanceReference.emptyArchive(loader), kitArchive = AppearanceReference.emptyArchive(loader);
            int highest = 0;
            List<Path> modelPaths;
            try (var paths = Files.list(models)) { modelPaths = paths.filter(p -> p.toString().endsWith(".dat")).toList(); }
            for (Path p : modelPaths) highest = Math.max(highest, Integer.parseInt(p.getFileName().toString().replace(".dat", "")));
            Object[][] modelFiles = new Object[highest + 1][];
            for (Path p : modelPaths) modelFiles[Integer.parseInt(p.getFileName().toString().replace(".dat", ""))] = new Object[]{Files.readAllBytes(p)};
            AppearanceReference.field(archive, "u").set(modelArchive, modelFiles);
            Object[][] kitFiles = new Object[4][];
            kitFiles[3] = new Object[151];
            for (int id = 0; id < 151; id++) kitFiles[3][id] = Files.readAllBytes(kits.resolve(id + ".dat"));
            AppearanceReference.field(archive, "u").set(kitArchive, kitFiles);
            kit.getDeclaredMethod("w", archive, archive).invoke(null, kitArchive, modelArchive);
            Path items = args.length > 8 ? Path.of(args[8]) : null;
            if (items != null) {
                List<Path> itemPaths;
                try (var paths = Files.list(items)) { itemPaths = paths.filter(p -> p.toString().endsWith(".dat")).toList(); }
                Object[][] itemFiles = new Object[11][];
                itemFiles[10] = new Object[itemPaths.stream().mapToInt(SequenceReference::id).max().orElseThrow() + 1];
                for (Path p : itemPaths) itemFiles[10][SequenceReference.id(p)] = Files.readAllBytes(p);
                Object itemArchive = AppearanceReference.emptyArchive(loader);
                AppearanceReference.field(archive, "u").set(itemArchive, itemFiles);
                AppearanceReference.field(loader.loadClass("eb"), "e").set(null, itemArchive);
                AppearanceReference.field(loader.loadClass("iz"), "l").set(null, modelArchive);
            }
            Class<?> hv = Class.forName("hv", true, loader);
            AppearanceReference.field(appearance, "l").set(null, AppearanceReference.field(hv, "a").get(null));
            AppearanceReference.field(appearance, "w").set(null, AppearanceReference.field(hv, "n").get(null));
            AppearanceReference.field(loader.loadClass("gw"), "s").set(null, AppearanceReference.field(hv, "j").get(null));
            AppearanceReference.field(loader.loadClass("cd"), "p").set(null, AppearanceReference.field(hv, "r").get(null));

            // Frames in index 0 and frame maps in index 1, as the client's two static archives. Each group lists all
            // of its files that the clip uses, which is what cd.m loads through if.g.
            Class<?> sequence = loader.loadClass("jg");
            Object frames = AppearanceReference.emptyArchive(loader), maps = AppearanceReference.emptyArchive(loader);
            String manifest = Files.readString(clip.resolve("manifest.json"));
            List<int[]> ids = new ArrayList<>();
            var matcher = java.util.regex.Pattern.compile("\"group\": (\\d+),\\s*\"file\": (\\d+),\\s*\"map\": (\\d+)").matcher(manifest);
            while (matcher.find()) ids.add(new int[]{Integer.parseInt(matcher.group(1)), Integer.parseInt(matcher.group(2)), Integer.parseInt(matcher.group(3))});
            if (ids.isEmpty()) throw new IllegalStateException("The clip manifest lists no frames");
            int highestGroup = ids.stream().mapToInt(i -> i[0]).max().orElseThrow();
            Object[][] frameFiles = new Object[highestGroup + 1][];
            int[][] frameFileIds = new int[highestGroup + 1][];
            Map<Integer, TreeSet<Integer>> filesByGroup = new TreeMap<>();
            for (int[] id : ids) filesByGroup.computeIfAbsent(id[0], g -> new TreeSet<>()).add(id[1]);
            for (var entry : filesByGroup.entrySet()) {
                int group = entry.getKey();
                frameFiles[group] = new Object[entry.getValue().last() + 1];
                frameFileIds[group] = entry.getValue().stream().mapToInt(Integer::intValue).toArray();
                for (int file : entry.getValue()) frameFiles[group][file] = Files.readAllBytes(clip.resolve("frames").resolve(group + "_" + file + ".dat"));
            }
            AppearanceReference.field(archive, "u").set(frames, frameFiles);
            AppearanceReference.field(archive, "s").set(frames, frameFileIds);
            int highestMap = ids.stream().mapToInt(i -> i[2]).max().orElseThrow();
            Object[][] mapFiles = new Object[highestMap + 1][];
            for (int[] id : ids) mapFiles[id[2]] = new Object[]{Files.readAllBytes(clip.resolve("maps").resolve(id[2] + ".dat"))};
            AppearanceReference.field(archive, "u").set(maps, mapFiles);
            AppearanceReference.field(sequence, "j").set(null, frames);
            AppearanceReference.field(loader.loadClass("ah"), "n").set(null, maps);

            int[] packed = ids.stream().mapToInt(i -> (i[0] << 16) | i[1]).toArray();
            Object clipSequence;
            if (items == null) {
                clipSequence = allocate(loader, "jg");
                AppearanceReference.field(sequence, "e").set(clipSequence, packed);
            } else {
                Object[][] configFiles = new Object[13][];
                configFiles[12] = new Object[]{Files.readAllBytes(clip.resolve("sequence.dat"))};
                Object configs = AppearanceReference.emptyArchive(loader);
                AppearanceReference.field(archive, "u").set(configs, configFiles);
                AppearanceReference.field(sequence, "a").set(null, configs);
                var load = loader.loadClass("du").getDeclaredMethod("j", int.class, byte.class);
                load.setAccessible(true);
                clipSequence = load.invoke(null, 0, (byte)-93);
                if (!Arrays.equals((int[]) AppearanceReference.field(sequence, "e").get(clipSequence), packed))
                    throw new IllegalStateException("The decoded sequence's frames differ from the manifest");
            }

            Map<String,Object> result = new LinkedHashMap<>();
            result.put("rest", vertices(posed(appearance, sequence, null, 0, equipment, colours, female)));
            List<Object> poses = new ArrayList<>();
            for (int frame = 0; frame < packed.length; frame++) poses.add(vertices(posed(appearance, sequence, clipSequence, frame, equipment, colours, female)));
            result.put("frames", poses);
            Files.writeString(output, AppearanceReference.json(result) + "\n");
        }
    }

    static Object allocate(ClassLoader loader, String type) throws Exception {
        Class<?> unsafe = Class.forName("sun.misc.Unsafe");
        Object allocator = AppearanceReference.field(unsafe, "theUnsafe").get(null);
        return unsafe.getMethod("allocateInstance", Class.class).invoke(allocator, loader.loadClass(type));
    }

    static Object posed(Class<?> appearance, Class<?> sequence, Object action, int frame, int[] equipment, int[] colours, boolean female) throws Exception {
        Object player = appearance.getDeclaredConstructor().newInstance();
        appearance.getDeclaredMethod("a", int[].class, int[].class, boolean.class, int.class, int.class)
            .invoke(player, equipment.clone(), colours.clone(), female, -1, 0);
        Object model = appearance.getDeclaredMethod("l", sequence, int.class, sequence, int.class, byte.class)
            .invoke(player, action, frame, null, 0, (byte)127);
        if (model == null) throw new IllegalStateException("Client returned no model");
        return model;
    }

    // ej.v is the vertex count and ej.w the face count; e, l and s are vertex x, y and z, and o holds face alphas.
    // An animated model's arrays are buffers the client reuses for the next frame and sizes past the counts, so each
    // is copied at its count when recorded.
    static Map<String,Object> vertices(Object model) throws Exception {
        Map<String,Object> out = new LinkedHashMap<>();
        int count = AppearanceReference.field(model.getClass(), "v").getInt(model);
        int faces = AppearanceReference.field(model.getClass(), "w").getInt(model);
        out.put("vertex_count", count);
        out.put("face_count", faces);
        for (String name : List.of("e", "l", "s")) {
            int[] all = (int[]) AppearanceReference.field(model.getClass(), name).get(model);
            out.put(name, Arrays.copyOf(all, count));
        }
        byte[] alphas = (byte[]) AppearanceReference.field(model.getClass(), "o").get(model);
        out.put("o", alphas == null ? null : Arrays.copyOf(alphas, faces));
        return out;
    }
}
