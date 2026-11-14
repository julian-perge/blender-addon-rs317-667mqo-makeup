import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.StringJoiner;
import java.util.zip.GZIPOutputStream;
import net.runelite.cache.definitions.LocationsDefinition;
import net.runelite.cache.definitions.MapDefinition;
import net.runelite.cache.definitions.loaders.LocationsLoader;
import net.runelite.cache.definitions.loaders.MapLoader;
import net.runelite.cache.fs.Container;
import net.runelite.cache.region.Location;
import net.runelite.cache.region.Region;

/**
 * Reads parts of a region with RuneLite's cache library and writes what it read.
 *
 * The tests compare our region decoders against these files, so the expected values come from a second,
 * independent implementation. Each mode below writes one reference file. Later tasks of the region import add one mode each.
 *
 * Run with a class path that holds RuneLite's cache library (net.runelite:cache) and the jars that `Container` needs
 * (Guava 23.2-jre, slf4j-api 1.7.36 and commons-compress 1.26.2, all in a Maven repository):
 * java -cp <class path> tests/fixtures/RegionReference.java landscape <group file> <key file> <output json>
 * java -cp <class path> tests/fixtures/RegionReference.java terrain <group file> <region x> <region y> <output txt.gz>
 *
 * The landscape mode was run with cache library 1.13.6. The terrain mode must run with cache library 1.9.0
 * (repo.runelite.net), because the commit "cache: update 209" (aef9c8fa5, 7 October 2022) made `MapLoader` read each
 * terrain opcode as 16 bits, and snapshot 430 stores them as 8 bits. With 1.13.6 the terrain mode reads past the end of
 * the group. `Region.loadTerrain` and `HeightCalc` are the same in both versions. With cache library 1.9.0, use
 * commons-compress 1.10, the version that its pom names: commons-compress 1.26.2 also needs commons-io.
 *
 * landscape: decrypts and decompresses one landscape group (`l<x>_<y>`, as the cache stores it) with the four keys of
 * the key file (one number per line), reads its placements with LocationsLoader and writes them in file order. Each
 * placement is the loc id, the level, the x and y of its tile inside the region, the loc type and the rotation.
 *
 * terrain: decompresses one terrain group (`m<x>_<y>`, as the cache stores it), reads it with MapLoader and
 * Region.loadTerrain, as RegionLoader.loadRegionFromArchive does, and writes a gzip text file with one line for each
 * tile of each level: the height, the settings, the underlay, the overlay, the overlay shape, the overlay rotation, and
 * 1 when the group stores a height for the tile or 0 when `Region.loadTerrain` takes it from `HeightCalc` or the level below.
 * The lines go by level from 0 to 3, then by x from 0 to 63, then by y from 0 to 63, so line
 * `level * 4096 + x * 64 + y` holds tile (x, y) of that level. The file has no tile numbers, which keeps it 4 times smaller.
 */
public class RegionReference {
    public static void main(String[] args) throws Exception {
        if (args.length == 4 && args[0].equals("landscape")) {
            landscape(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
        } else if (args.length == 5 && args[0].equals("terrain")) {
            terrain(Path.of(args[1]), Integer.parseInt(args[2]), Integer.parseInt(args[3]), Path.of(args[4]));
        } else {
            throw new IllegalArgumentException(
                "Usage: landscape <group file> <key file> <output json>"
                    + " | terrain <group file> <region x> <region y> <output txt.gz>");
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

    static void terrain(Path group, int regionX, int regionY, Path output) throws Exception {
        byte[] data = Container.decompress(Files.readAllBytes(group), null).data;
        MapDefinition map = new MapLoader().load(regionX, regionY, data);
        // The region numbers place the tiles in the world, which the height of a tile with no stored height needs.
        Region region = new Region(regionX, regionY);
        region.loadTerrain(map);
        try (Writer out = new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(output)),
                StandardCharsets.US_ASCII)) {
            for (int z = 0; z < Region.Z; z++) {
                for (int x = 0; x < Region.X; x++) {
                    for (int y = 0; y < Region.Y; y++) {
                        out.write(String.format("%d %d %d %d %d %d %d\n", region.getTileHeight(z, x, y),
                            region.getTileSetting(z, x, y), region.getUnderlayId(z, x, y),
                            region.getOverlayId(z, x, y), region.getOverlayPath(z, x, y),
                            region.getOverlayRotation(z, x, y), map.getTiles()[z][x][y].height == null ? 0 : 1));
                    }
                }
            }
        }
    }
}
