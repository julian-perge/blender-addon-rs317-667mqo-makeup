import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Runs the unchanged revision-149 NPC model pipeline for each raw NPC definition and records the lit, scaled model.
 *
 * Class `ip` is the 2018 client's NPCComposition. `ip.m(int)` reads file `id` of config group 9 from the archive `ip.a`
 * and decodes it. `ip.v(jg,int,jg,int,int)` is getModel: with null sequences it loads each model of opcode 1 from the
 * model archive `gw.j` (offsets 297-311 and 457-475), merges them (offset 202), recolours (offsets 630-646) and
 * retextures (offsets 592-608), lights with `dv.ae` and the NPC's ambient and contrast (offsets 418-449),
 * copies the lit model (offset 575) and scales it by `ej.i(widthScale, heightScale, widthScale)` (offsets 712-738).
 *
 * args: client jar, folder of raw NPC files `<id>.dat`, folder of raw model files `<id>.dat`, output file.
 */
public final class NpcModelReference {
    // The guard value that ip.v compares its last argument against before it runs (offsets 8-13).
    static final int GET_MODEL_GUARD = -1462771291;

    public static void main(String[] args) throws Exception {
        Path npcs = Path.of(args[1]), models = Path.of(args[2]), output = Path.of(args[3]);
        try (var loader = new URLClassLoader(new URL[]{Path.of(args[0]).toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            Class<?> archive = loader.loadClass("if"), npc = loader.loadClass("ip");
            Object modelArchive = AppearanceReference.emptyArchive(loader), configArchive = AppearanceReference.emptyArchive(loader);
            AppearanceReference.field(archive, "u").set(modelArchive, files(models, true));
            Object[][] configFiles = new Object[10][];
            configFiles[9] = files(npcs, false)[0];
            AppearanceReference.field(archive, "u").set(configArchive, configFiles);
            AppearanceReference.field(npc, "a").set(null, configArchive);
            AppearanceReference.field(loader.loadClass("gw"), "j").set(null, modelArchive);

            Map<String,Object> result = new TreeMap<>(Comparator.comparingInt(Integer::parseInt));
            for (int id : ids(npcs)) {
                var definition = npc.getDeclaredMethod("m", int.class).invoke(null, id);
                var getModel = npc.getDeclaredMethod("v", loader.loadClass("jg"), int.class, loader.loadClass("jg"), int.class, int.class);
                Object model = getModel.invoke(definition, null, 0, null, 0, GET_MODEL_GUARD);
                if (model == null) throw new IllegalStateException("The client returned no model for NPC " + id);
                result.put(Integer.toString(id), lit(model));
            }
            Files.writeString(output, AppearanceReference.json(result) + "\n");
        }
    }

    // With `perGroup`, each file becomes file 0 of the group with its id, as the model archive stores models. Without,
    // all files go into one group, each at the index of its id, as config group 9 stores NPCs.
    static Object[][] files(Path folder, boolean perGroup) throws Exception {
        List<Integer> ids = ids(folder);
        int highest = ids.stream().mapToInt(Integer::intValue).max().orElseThrow();
        Object[][] out = new Object[perGroup ? highest + 1 : 1][];
        if (!perGroup) out[0] = new Object[highest + 1];
        for (int id : ids) {
            byte[] data = Files.readAllBytes(folder.resolve(id + ".dat"));
            if (perGroup) out[id] = new Object[]{data}; else out[0][id] = data;
        }
        return out;
    }

    static List<Integer> ids(Path folder) throws Exception {
        try (var paths = Files.list(folder)) {
            return paths.map(p -> p.getFileName().toString()).filter(n -> n.endsWith(".dat"))
                .map(n -> Integer.parseInt(n.substring(0, n.length() - 4))).sorted().toList();
        }
    }

    // ej.v is the vertex count and ej.w the face count; e, l and s are vertex x, y and z; g, k and t are the lit
    // colours of the three corners of each face (tests/fixtures/appearance/README.md, "Field contract"). The arrays
    // are copied at their counts, because the client can size them past the counts.
    static Map<String,Object> lit(Object model) throws Exception {
        Map<String,Object> out = new LinkedHashMap<>();
        int vertices = AppearanceReference.field(model.getClass(), "v").getInt(model);
        int faces = AppearanceReference.field(model.getClass(), "w").getInt(model);
        out.put("vertex_count", vertices);
        out.put("face_count", faces);
        for (String name : List.of("e", "l", "s")) {
            out.put(name, Arrays.copyOf((int[]) AppearanceReference.field(model.getClass(), name).get(model), vertices));
        }
        for (String name : List.of("g", "k", "t")) {
            out.put(name, Arrays.copyOf((int[]) AppearanceReference.field(model.getClass(), name).get(model), faces));
        }
        return out;
    }
}
