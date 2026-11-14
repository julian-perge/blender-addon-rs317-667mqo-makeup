import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.StringJoiner;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import java.util.zip.GZIPOutputStream;
import net.runelite.cache.definitions.LocationsDefinition;
import net.runelite.cache.definitions.MapDefinition;
import net.runelite.cache.definitions.ObjectDefinition;
import net.runelite.cache.definitions.OverlayDefinition;
import net.runelite.cache.definitions.UnderlayDefinition;
import net.runelite.cache.definitions.loaders.LocationsLoader;
import net.runelite.cache.definitions.loaders.MapLoader;
import net.runelite.cache.definitions.loaders.ObjectLoader;
import net.runelite.cache.definitions.loaders.OverlayLoader;
import net.runelite.cache.definitions.loaders.UnderlayLoader;
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
 * java -cp <class path> tests/fixtures/RegionReference.java floors <underlay folder> <overlay folder> <output json>
 * java -cp <class path> tests/fixtures/RegionReference.java locs <loc folder> <archive revision> <output json>
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
 *
 * The floors and locs modes were run with cache library 1.13.6. Each folder holds one raw definition file per id,
 * `<id>.dat`, as config groups 1 (underlays), 4 (overlays) and 6 (locs) of index 2 store them.
 *
 * floors: reads each underlay with UnderlayLoader and each overlay with OverlayLoader, and writes their fields,
 * and the hue, saturation and lightness that the loaders compute from them, by id.
 *
 * locs: reads each loc with ObjectLoader and writes the fields that the region import keeps, by id. The archive revision
 * is the revision of config group 6 in the reference table of index 2 (988 in snapshot 430). It goes to
 * `configureForRevision`, as `ObjectManager` gives it, because the loader reads opcodes 78 and 79 with one more byte
 * from revision 1673 on. The recolours and retextures are written as the signed shorts that the loader keeps, and the
 * offsets as the unsigned shorts that it reads.
 */
public class RegionReference {
    public static void main(String[] args) throws Exception {
        if (args.length == 4 && args[0].equals("landscape")) {
            landscape(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
        } else if (args.length == 5 && args[0].equals("terrain")) {
            terrain(Path.of(args[1]), Integer.parseInt(args[2]), Integer.parseInt(args[3]), Path.of(args[4]));
        } else if (args.length == 4 && args[0].equals("floors")) {
            floors(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
        } else if (args.length == 4 && args[0].equals("locs")) {
            locs(Path.of(args[1]), Integer.parseInt(args[2]), Path.of(args[3]));
        } else {
            throw new IllegalArgumentException(
                "Usage: landscape <group file> <key file> <output json>"
                    + " | terrain <group file> <region x> <region y> <output txt.gz>"
                    + " | floors <underlay folder> <overlay folder> <output json>"
                    + " | locs <loc folder> <archive revision> <output json>");
        }
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

    static void floors(Path underlays, Path overlays, Path output) throws Exception {
        StringJoiner under = new StringJoiner(",\n    ", "[\n    ", "\n  ]");
        for (int id : ids(underlays)) {
            UnderlayDefinition d = new UnderlayLoader().load(id, Files.readAllBytes(underlays.resolve(id + ".dat")));
            under.add(String.format("{\"id\": %d, \"color\": %d, \"hue\": %d, \"saturation\": %d, \"lightness\": %d,"
                + " \"hueMultiplier\": %d}", id, d.getColor(), d.getHue(), d.getSaturation(), d.getLightness(),
                d.getHueMultiplier()));
        }
        StringJoiner over = new StringJoiner(",\n    ", "[\n    ", "\n  ]");
        for (int id : ids(overlays)) {
            OverlayDefinition d = new OverlayLoader().load(id, Files.readAllBytes(overlays.resolve(id + ".dat")));
            over.add(String.format("{\"id\": %d, \"rgbColor\": %d, \"texture\": %d, \"hideUnderlay\": %b,"
                + " \"secondaryRgbColor\": %d, \"hue\": %d, \"saturation\": %d, \"lightness\": %d, \"otherHue\": %d,"
                + " \"otherSaturation\": %d, \"otherLightness\": %d}", id, d.getRgbColor(), d.getTexture(),
                d.isHideUnderlay(), d.getSecondaryRgbColor(), d.getHue(), d.getSaturation(), d.getLightness(),
                d.getOtherHue(), d.getOtherSaturation(), d.getOtherLightness()));
        }
        Files.writeString(output, "{\n  \"underlays\": " + under + ",\n  \"overlays\": " + over + "\n}\n");
    }

    static void locs(Path folder, int revision, Path output) throws Exception {
        StringJoiner out = new StringJoiner(",\n  ", "[\n  ", "\n]\n");
        for (int id : ids(folder)) {
            ObjectDefinition d = new ObjectLoader().configureForRevision(revision)
                .load(id, Files.readAllBytes(folder.resolve(id + ".dat")));
            out.add(String.format("{\"id\": %d, \"objectModels\": %s, \"objectTypes\": %s, \"sizeX\": %d, \"sizeY\": %d,"
                + " \"recolorToFind\": %s, \"recolorToReplace\": %s, \"retextureToFind\": %s, \"textureToReplace\": %s,"
                + " \"modelSizeX\": %d, \"modelSizeHeight\": %d, \"modelSizeY\": %d, \"offsetX\": %d,"
                + " \"offsetHeight\": %d, \"offsetY\": %d, \"isRotated\": %b, \"contouredGround\": %d,"
                + " \"mergeNormals\": %b, \"animationID\": %d, \"decorDisplacement\": %d, \"shadow\": %b,"
                + " \"varbitID\": %d, \"varpID\": %d, \"configChangeDest\": %s}",
                id, json(d.getObjectModels()), json(d.getObjectTypes()), d.getSizeX(), d.getSizeY(),
                json(d.getRecolorToFind()), json(d.getRecolorToReplace()), json(d.getRetextureToFind()),
                json(d.getTextureToReplace()), d.getModelSizeX(), d.getModelSizeHeight(), d.getModelSizeY(),
                d.getOffsetX(), d.getOffsetHeight(), d.getOffsetY(), d.isRotated(), d.getContouredGround(),
                d.isMergeNormals(), d.getAnimationID(), d.getDecorDisplacement(), d.isShadow(), d.getVarbitID(),
                d.getVarpID(), json(d.getConfigChangeDest())));
        }
        Files.writeString(output, out.toString());
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
