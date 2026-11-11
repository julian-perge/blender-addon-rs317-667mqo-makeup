import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Decodes sequence files with the unchanged revision-149 loader du.j and steps the unchanged per-tick actor update
 * ap.fb, recording the decoded fields and the frame shown after each tick.
 */
public final class SequenceReference {
    // args: client jar, folder of <id>.dat sequence files, output file, then timing cases as id:pose:ticks or
    // id:action:ticks
    public static void main(String[] args) throws Exception {
        Path folder = Path.of(args[1]), output = Path.of(args[2]);
        try (var loader = new URLClassLoader(new URL[]{Path.of(args[0]).toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            Class<?> archive = loader.loadClass("if"), sequence = loader.loadClass("jg");
            List<Path> files;
            try (var paths = Files.list(folder)) { files = paths.filter(p -> p.toString().endsWith(".dat")).toList(); }
            int highest = files.stream().mapToInt(SequenceReference::id).max().orElseThrow();
            Object[][] configFiles = new Object[13][];
            configFiles[12] = new Object[highest + 1];
            for (Path p : files) configFiles[12][id(p)] = Files.readAllBytes(p);
            Object configs = AppearanceReference.emptyArchive(loader);
            AppearanceReference.field(archive, "u").set(configs, configFiles);
            AppearanceReference.field(sequence, "a").set(null, configs);
            var load = loader.loadClass("du").getDeclaredMethod("j", int.class, byte.class);
            load.setAccessible(true);

            Map<String,Object> decoded = new TreeMap<>(Comparator.comparingInt(Integer::parseInt));
            for (Path p : files) decoded.put(String.valueOf(id(p)), fields(sequence, load.invoke(null, id(p), (byte)-93)));
            List<Object> timing = new ArrayList<>();
            for (int i = 3; i < args.length; i++) {
                String[] parts = args[i].split(":");
                timing.add(steps(loader, load, Integer.parseInt(parts[0]), parts[1], Integer.parseInt(parts[2])));
            }
            Map<String,Object> result = new LinkedHashMap<>();
            result.put("sequences", decoded);
            result.put("timing", timing);
            Files.writeString(output, AppearanceReference.json(result) + "\n");
        }
    }

    static int id(Path p) { return Integer.parseInt(p.getFileName().toString().replace(".dat", "")); }

    // Each multiplier is the one the client itself applies when it reads the field (for example 964163047 for jg.o in
    // jg.v and ap.fb), so the values are the decoded numbers, not the obfuscated stored ones.
    static Map<String,Object> fields(Class<?> sequence, Object s) throws Exception {
        Map<String,Object> out = new LinkedHashMap<>();
        out.put("frames", AppearanceReference.field(sequence, "e").get(s));
        out.put("durations", AppearanceReference.field(sequence, "s").get(s));
        out.put("loop_offset", 1652071589 * AppearanceReference.field(sequence, "p").getInt(s));
        out.put("interleave", AppearanceReference.field(sequence, "m").get(s));
        out.put("stretches", AppearanceReference.field(sequence, "u").getBoolean(s));
        out.put("forced_priority", -1748349517 * AppearanceReference.field(sequence, "g").getInt(s));
        out.put("left_hand_item", -1791941913 * AppearanceReference.field(sequence, "k").getInt(s));
        out.put("right_hand_item", -1221517269 * AppearanceReference.field(sequence, "t").getInt(s));
        out.put("max_loops", -1695295085 * AppearanceReference.field(sequence, "c").getInt(s));
        out.put("precedence_animating", 964163047 * AppearanceReference.field(sequence, "o").getInt(s));
        out.put("priority", 865985193 * AppearanceReference.field(sequence, "x").getInt(s));
        out.put("reply_mode", -153357275 * AppearanceReference.field(sequence, "f").getInt(s));
        out.put("chat_frames", AppearanceReference.field(sequence, "l").get(s));
        out.put("frame_sounds", AppearanceReference.field(sequence, "w").get(s));
        return out;
    }

    /** The multiplicative inverse modulo 2^32 of an odd multiplier, by Newton's iteration. */
    static int inverse(int value) {
        int x = value;
        for (int i = 0; i < 5; i++) x *= 2 - value * x;
        return x;
    }

    // The actor fields are declared on the abstract actor class ca, the superclass of the player class be.
    static void set(Object actor, String name, int decoded, int multiplier) throws Exception {
        AppearanceReference.field(actor.getClass().getSuperclass(), name).setInt(actor, decoded * inverse(multiplier));
    }

    static int get(Object actor, String name, int multiplier) throws Exception {
        return multiplier * AppearanceReference.field(actor.getClass().getSuperclass(), name).getInt(actor);
    }

    // The actor is a constructor-free player (class be). ap.fb takes its first branch, which only moves the actor
    // toward its own position, because ca.be is far past client.bw; the actor stays inside the 128 to 13184 square
    // whose exit would clear the action sequence. Turning is off (ca.ct 0) and no spot animation runs (ca.bg -1).
    static Map<String,Object> steps(ClassLoader loader, java.lang.reflect.Method load, int id, String mode, int ticks) throws Exception {
        if (!mode.equals("pose") && !mode.equals("action")) throw new IllegalArgumentException("Mode must be pose or action");
        Object actor = PoseReference.allocate(loader, "be");
        set(actor, "be", 1_000_000, 1092566373);
        set(actor, "ae", 6400, 1788873965);
        set(actor, "au", 6400, 989311819);
        set(actor, "bg", -1, -1949670241);
        set(actor, "bc", mode.equals("pose") ? id : -1, -1915867089);
        set(actor, "bs", mode.equals("action") ? id : -1, -2041620275);
        var update = loader.loadClass("ap").getDeclaredMethod("fb", loader.loadClass("ca"), int.class, int.class);
        update.setAccessible(true);
        List<Integer> frames = new ArrayList<>();
        frames.add(0);
        for (int tick = 1; tick <= ticks; tick++) {
            update.invoke(null, actor, 1, -2068043986);
            if (mode.equals("pose")) {
                if (get(actor, "bc", -1915867089) != id) throw new IllegalStateException("The pose sequence changed");
                frames.add(get(actor, "bb", 1746811053));
            } else {
                frames.add(get(actor, "bs", -2041620275) == id ? get(actor, "bh", 1128972655) : -1);
            }
        }
        Map<String,Object> out = new LinkedHashMap<>();
        out.put("sequence", id);
        out.put("mode", mode);
        out.put("frames", frames);
        return out;
    }
}
