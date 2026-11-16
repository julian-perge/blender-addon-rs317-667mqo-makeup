import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.StringJoiner;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import net.runelite.cache.definitions.NpcDefinition;
import net.runelite.cache.definitions.loaders.NpcLoader;

/**
 * Reads NPC definitions with RuneLite's cache library and writes the fields that the NPC decoder keeps.
 *
 * The tests compare `formats/npc_definition.py` against this file, so the expected values come from a second,
 * independent implementation. Run with cache library 1.13.6 and the jars that it needs (lombok is not needed at run
 * time, slf4j-api 1.7.36 is):
 * java -cp <class path> tests/fixtures/NpcReference.java <npc folder> <archive revision> <output json>
 *
 * The folder holds one raw definition file per id, `<id>.dat`, as config group 9 of index 2 stores them. The archive
 * revision is the revision of config group 9 in the reference table of index 2 (959 in snapshot 430). It goes to
 * `configureForRevision`, because the loader reads opcode 102 in another form from archive revision 1493 on.
 *
 * The fields keep RuneLite's names. The recolours and retextures are written as the signed shorts that the loader
 * keeps.
 */
public class NpcReference {
    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: <npc folder> <archive revision> <output json>");
        }
        Path folder = Path.of(args[0]);
        int revision = Integer.parseInt(args[1]);
        StringJoiner out = new StringJoiner(",\n  ", "[\n  ", "\n]\n");
        for (int id : ids(folder)) {
            NpcDefinition d = new NpcLoader().configureForRevision(revision)
                .load(id, Files.readAllBytes(folder.resolve(id + ".dat")));
            out.add(String.format("{\"id\": %d, \"name\": \"%s\", \"models\": %s, \"standingAnimation\": %d,"
                + " \"walkingAnimation\": %d, \"idleRotateLeftAnimation\": %d, \"idleRotateRightAnimation\": %d,"
                + " \"rotate180Animation\": %d, \"rotateLeftAnimation\": %d, \"rotateRightAnimation\": %d,"
                + " \"recolorToFind\": %s, \"recolorToReplace\": %s, \"retextureToFind\": %s,"
                + " \"retextureToReplace\": %s, \"widthScale\": %d, \"heightScale\": %d, \"ambient\": %d,"
                + " \"contrast\": %d}",
                id, d.getName().replace("\\", "\\\\").replace("\"", "\\\""), json(d.getModels()),
                d.getStandingAnimation(), d.getWalkingAnimation(), d.getIdleRotateLeftAnimation(),
                d.getIdleRotateRightAnimation(), d.getRotate180Animation(), d.getRotateLeftAnimation(),
                d.getRotateRightAnimation(), json(d.getRecolorToFind()), json(d.getRecolorToReplace()),
                json(d.getRetextureToFind()), json(d.getRetextureToReplace()), d.getWidthScale(),
                d.getHeightScale(), d.getAmbient(), d.getContrast()));
        }
        Files.writeString(Path.of(args[2]), out.toString());
    }

    static List<Integer> ids(Path folder) throws Exception {
        try (var paths = Files.list(folder)) {
            return paths.map(p -> p.getFileName().toString()).filter(n -> n.endsWith(".dat"))
                .map(n -> Integer.parseInt(n.substring(0, n.length() - 4))).sorted().collect(Collectors.toList());
        }
    }

    static String json(int[] values) {
        return values == null ? "null" : Arrays.toString(values);
    }

    static String json(short[] values) {
        return values == null ? "null"
            : IntStream.range(0, values.length).mapToObj(i -> Short.toString(values[i]))
                .collect(Collectors.joining(", ", "[", "]"));
    }
}
