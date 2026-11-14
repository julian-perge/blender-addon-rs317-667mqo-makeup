import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.StringJoiner;
import net.runelite.cache.definitions.LocationsDefinition;
import net.runelite.cache.definitions.loaders.LocationsLoader;
import net.runelite.cache.fs.Container;
import net.runelite.cache.region.Location;

/**
 * Reads parts of a region with RuneLite's cache library and writes what it read as JSON.
 *
 * The tests compare our region decoders against these files, so the expected values come from a second,
 * independent implementation. Each mode below writes one reference file. Later tasks of the region import add one mode each.
 *
 * Run with a class path that holds RuneLite's cache library 1.13.6 (net.runelite:cache) and the jars that `Container` needs
 * (Guava 23.2-jre, slf4j-api 1.7.36 and commons-compress 1.26.2, all in a Maven repository):
 * java -cp <class path> tests/fixtures/RegionReference.java landscape <group file> <key file> <output json>
 *
 * landscape: decrypts and decompresses one landscape group (`l<x>_<y>`, as the cache stores it) with the four keys of
 * the key file (one number per line), reads its placements with LocationsLoader and writes them in file order. Each
 * placement is the loc id, the level, the x and y of its tile inside the region, the loc type and the rotation.
 */
public class RegionReference {
    public static void main(String[] args) throws Exception {
        if (args.length == 4 && args[0].equals("landscape")) {
            landscape(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
        } else {
            throw new IllegalArgumentException("Usage: landscape <group file> <key file> <output json>");
        }
    }

    static void landscape(Path group, Path keyFile, Path output) throws Exception {
        int[] keys = Files.readAllLines(keyFile).stream().map(String::trim).filter(s -> !s.isEmpty())
            .mapToInt(Integer::parseInt).toArray();
        if (keys.length != 4) throw new IllegalArgumentException(keyFile + " does not hold four numbers");
        byte[] data = Container.decompress(Files.readAllBytes(group), keys).data;
        // The region numbers only label the definition. The placements carry tile numbers inside the region.
        LocationsDefinition definition = new LocationsLoader().load(0, 0, data);
        List<Location> locations = definition.getLocations();
        StringJoiner json = new StringJoiner(",\n  ", "[\n  ", "\n]\n");
        for (Location l : locations) {
            json.add(String.format("{\"id\": %d, \"level\": %d, \"x\": %d, \"y\": %d, \"type\": %d, \"rotation\": %d}",
                l.getId(), l.getPosition().getZ(), l.getPosition().getX(), l.getPosition().getY(), l.getType(),
                l.getOrientation()));
        }
        Files.writeString(output, json.toString());
    }
}
