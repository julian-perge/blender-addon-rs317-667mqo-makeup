import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import net.runelite.cache.fs.Archive;
import net.runelite.cache.fs.FSFile;
import net.runelite.cache.fs.Index;
import net.runelite.cache.fs.Store;

public final class AnimationReference {
    private static final Gson JSON = new GsonBuilder().serializeNulls().setPrettyPrinting().create();

    private static final class ArchiveSource extends Class61 {
        private final Store store;
        private final Index index;
        private final int indexId;
        private final Path raw;
        private final Map<Integer, Map<Integer, byte[]>> loaded = new TreeMap<>();
        private final Map<Integer, Set<Integer>> requested = new TreeMap<>();

        ArchiveSource(Store store, int indexId, Path root) {
            super(false, false);
            this.store = store;
            this.indexId = indexId;
            raw = store == null ? root.resolve("raw").resolve(Integer.toString(indexId)) : null;
            index = store == null ? null : store.findIndex(indexId);
            if (store != null && index == null) throw new IllegalArgumentException("Missing cache index " + indexId);
        }

        private Map<Integer, byte[]> files(int group) {
            return loaded.computeIfAbsent(group, id -> {
                Map<Integer, byte[]> result = new TreeMap<>();
                try {
                    if (raw != null) {
                        Path folder = raw.resolve(Integer.toString(id));
                        if (!Files.isDirectory(folder)) return result;
                        try (var paths = Files.list(folder)) {
                            for (Path path : paths.sorted().toList()) {
                                String name = path.getFileName().toString();
                                if (name.endsWith(".dat")) {
                                    result.put(Integer.parseInt(name.substring(0, name.length() - 4)), Files.readAllBytes(path));
                                }
                            }
                        }
                        return result;
                    }
                    Archive archive = index.getArchive(id);
                    if (archive == null) return result;
                    byte[] packed = store.getStorage().loadArchive(archive);
                    if (packed == null) throw new IllegalStateException("Missing archive data " + id);
                    for (FSFile file : archive.getFiles(packed).getFiles()) {
                        result.put(file.getFileId(), file.getContents());
                    }
                    return result;
                } catch (IOException error) {
                    throw new java.io.UncheckedIOException(error);
                }
            });
        }

        @Override public byte[] decompress(int group, int file) {
            byte[] bytes = files(group).get(file);
            if (bytes != null) requested.computeIfAbsent(group, id -> new TreeSet<>()).add(file);
            return bytes;
        }
        @Override public byte[] method262(int group, int file) { return decompress(group, file); }
        @Override public boolean exists(int group, int file) { return decompress(group, file) != null; }
        @Override public int[] method265(int group) {
            return files(group).keySet().stream().mapToInt(Integer::intValue).toArray();
        }
        @Override public int leng(int group) {
            return files(group).keySet().stream().mapToInt(Integer::intValue).max().orElse(-1) + 1;
        }
        @Override public int method267() {
            if (raw != null) {
                try (var paths = Files.list(raw)) {
                    return paths.mapToInt(path -> Integer.parseInt(path.getFileName().toString())).max().orElse(-1) + 1;
                } catch (IOException error) {
                    throw new java.io.UncheckedIOException(error);
                }
            }
            return index.getArchives().stream().mapToInt(Archive::getArchiveId).max().orElse(-1) + 1;
        }

        void record(Path output, JsonArray resources) throws Exception {
            for (var group : loaded.entrySet()) {
                for (var file : group.getValue().entrySet()) {
                    if (!requested.getOrDefault(group.getKey(), Set.of()).contains(file.getKey())) continue;
                    String relative = "raw/" + indexId + "/" + group.getKey() + "/" + file.getKey() + ".dat";
                    Path target = output.resolve(relative);
                    Files.createDirectories(target.getParent());
                    Files.write(target, file.getValue());
                    resources.add(JSON.toJsonTree(Map.of("index", indexId, "group", group.getKey(),
                        "file", file.getKey(), "path", relative, "sha256", hash(file.getValue()))));
                }
            }
        }
    }

    private static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static JsonElement canonical(JsonElement value) {
        if (value.isJsonObject()) {
            JsonObject result = new JsonObject();
            new TreeMap<>(value.getAsJsonObject().asMap()).forEach((key, entry) -> result.add(key, canonical(entry)));
            return result;
        }
        if (value.isJsonArray()) {
            JsonArray result = new JsonArray();
            value.getAsJsonArray().forEach(entry -> result.add(canonical(entry)));
            return result;
        }
        return value;
    }

    private static int[][] vertices(Class104_Sub18_Sub16_Sub4 model) {
        int[][] result = new int[model.anInt1529][3];
        for (int i = 0; i < result.length; i++) {
            result[i] = new int[] {model.anIntArray1530[i], model.anIntArray1531[i], model.anIntArray1584[i]};
        }
        return result;
    }

    private static int[][] vertices(Class104_Sub18_Sub16_Sub5 model) {
        int[][] result = new int[model.anInt1631][3];
        for (int i = 0; i < result.length; i++) {
            result[i] = new int[] {model.anIntArray1626[i], model.anIntArray1625[i], model.anIntArray1627[i]};
        }
        return result;
    }

    private static int[][] faces(Class104_Sub18_Sub16_Sub4 model) {
        int[][] result = new int[model.anInt1585][3];
        for (int i = 0; i < result.length; i++) {
            result[i] = new int[] {model.anIntArray1534[i], model.anIntArray1533[i], model.anIntArray1536[i]};
        }
        return result;
    }

    private static int[] alphas(Class104_Sub18_Sub16_Sub4 model) {
        int[] result = new int[model.anInt1585];
        if (model.aByteArray1535 != null) {
            for (int i = 0; i < result.length; i++) result[i] = model.aByteArray1535[i] & 255;
        }
        return result;
    }

    private static int[][] pairs(short[] from, short[] to) {
        int[][] result = new int[from == null ? 0 : from.length][2];
        for (int i = 0; i < result.length; i++) result[i] = new int[] {from[i] & 65535, to[i] & 65535};
        return result;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("cache-copy output-directory sequence-id");
        Path cache = Path.of(args[0]);
        Path out = Path.of(args[1]);
        int sequenceId = Integer.parseInt(args[2]);
        Files.createDirectories(out);
        try (Store store = Files.isDirectory(cache.resolve("raw")) ? null : new Store(cache.toFile())) {
            if (store != null) store.load();
            ArchiveSource frames = new ArchiveSource(store, 0, cache);
            ArchiveSource maps = new ArchiveSource(store, 1, cache);
            ArchiveSource configs = new ArchiveSource(store, 2, cache);
            ArchiveSource models = new ArchiveSource(store, 7, cache);
            ArchiveSource textures = new ArchiveSource(store, 9, cache);
            Class106.aClass61_829 = configs;
            Def2.aClass61_1391 = configs;
            Def2.aClass61_1394 = models;
            Class104_Sub2.ids = configs.leng(3);
            ItemDef.aClass61_1432 = configs;
            Class27.aClass61_265 = models;
            Class72.aClass61_584 = configs;
            Class7.aClass61_43 = frames;
            Def.aClass61_1259 = maps;
            Class57.aShortArray465 = Class97.aShortArray764;
            Class47.skinCols = Class97.aShortArrayArray763;
            Looks.aShortArray663 = Class97.aShortArray762;
            Looks.aShortArrayArray668 = Class97.aShortArrayArray765;

            Def sequence = Class70.forId(sequenceId);
            if (sequence.anIntArray1262 == null) throw new IllegalStateException("Missing sequence " + sequenceId);
            Looks appearance = new Looks();
            appearance.render(null, new int[] {0, 0, 0, 0, 0}, false, -1);
            int[] defaultEquipment = appearance.clothes.clone();
            int[] equipment = defaultEquipment.clone();
            equipment[3] = 512 + 4151;
            appearance.render(equipment, new int[] {0, 0, 0, 0, 0}, false, -1);

            JsonObject result = new JsonObject();
            result.addProperty("client_commit", "b0fdcde9c8bbbc75cd2ea4a3cd87461d1a62641b");
            result.addProperty("sequence_id", sequenceId);
            result.add("durations", JSON.toJsonTree(sequence.anIntArray1264));
            result.add("frame_ids", JSON.toJsonTree(sequence.anIntArray1262));
            result.addProperty("shield_override", sequence.anInt1270);
            result.addProperty("weapon_override", sequence.anInt1271);
            JsonObject fields = new JsonObject();
            fields.addProperty("anInt1266", sequence.anInt1266);
            fields.addProperty("anInt1261", sequence.anInt1261);
            fields.addProperty("anInt1269", sequence.anInt1269);
            fields.addProperty("anInt1273", sequence.anInt1273);
            fields.addProperty("anInt1274", sequence.anInt1274);
            fields.addProperty("anInt1275", sequence.anInt1275);
            fields.addProperty("aBool1272", sequence.aBool1272);
            fields.add("anIntArray1267", JSON.toJsonTree(sequence.anIntArray1267));
            fields.add("anIntArray1263", JSON.toJsonTree(sequence.anIntArray1263));
            fields.add("anIntArray1265", JSON.toJsonTree(sequence.anIntArray1265));
            result.add("client_sequence_fields", fields);
            result.add("default_equipment", JSON.toJsonTree(defaultEquipment));
            result.add("equipment", JSON.toJsonTree(equipment));
            result.add("appearance", JSON.toJsonTree(Map.of("female", false, "colors", appearance.skin)));

            int[] effective = equipment.clone();
            if (sequence.anInt1270 >= 0) effective[5] = sequence.anInt1270;
            if (sequence.anInt1271 >= 0) effective[3] = sequence.anInt1271;
            List<Class104_Sub18_Sub16_Sub5> parts = new ArrayList<>();
            JsonArray recipeParts = new JsonArray();
            for (int slot = 0; slot < effective.length; slot++) {
                int entry = effective[slot];
                Class104_Sub18_Sub16_Sub5 part = null;
                JsonObject details = new JsonObject();
                details.addProperty("slot", slot);
                details.addProperty("equipment_value", entry);
                if (entry >= 256 && entry < 512) {
                    Def2 kit = Class84.forId(entry - 256);
                    part = kit.method762();
                    details.addProperty("kit_id", entry - 256);
                    details.add("model_ids", JSON.toJsonTree(kit.anIntArray1395));
                    details.add("recolours", JSON.toJsonTree(pairs(kit.aShortArray1396, kit.aShortArray1397)));
                    details.add("retextures", JSON.toJsonTree(pairs(kit.aShortArray1398, kit.aShortArray1399)));
                } else if (entry >= 512) {
                    ItemDef item = Class27.forId(entry - 512);
                    part = item.method777(false);
                    details.addProperty("item_id", entry - 512);
                    details.add("model_ids", JSON.toJsonTree(new int[] {item.anInt1436, item.anInt1437, item.anInt1445}));
                    details.addProperty("offset_y", item.anInt1438);
                    details.add("recolours", JSON.toJsonTree(pairs(item.aShortArray1421, item.aShortArray1422)));
                    details.add("retextures", JSON.toJsonTree(pairs(item.aShortArray1423, item.aShortArray1424)));
                }
                if (part != null) {
                    details.addProperty("key", "slot-" + slot);
                    details.addProperty("face_count", part.anInt1628);
                    details.add("vertices", JSON.toJsonTree(vertices(part)));
                    recipeParts.add(details);
                    parts.add(part);
                }
            }
            Class104_Sub18_Sub16_Sub4 rest = appearance.method389(null, 0, null, 0);
            if (rest == null) throw new IllegalStateException("Client could not assemble player");
            int[][] restVertices = vertices(rest);
            Class104_Sub18_Sub16_Sub5 assembled = new Class104_Sub18_Sub16_Sub5(
                parts.toArray(new Class104_Sub18_Sub16_Sub5[0]), parts.size());
            for (int color = 0; color < appearance.skin.length; color++) {
                if (appearance.skin[color] < Class47.skinCols[color].length) {
                    assembled.method899(Class57.aShortArray465[color], Class47.skinCols[color][appearance.skin[color]]);
                }
                if (appearance.skin[color] < Looks.aShortArrayArray668[color].length) {
                    assembled.method899(Looks.aShortArray663[color], Looks.aShortArrayArray668[color][appearance.skin[color]]);
                }
            }
            if (!Arrays.deepEquals(vertices(assembled), restVertices)) {
                throw new IllegalStateException("Recorded assembly does not match Looks.method389");
            }
            JsonObject restData = new JsonObject();
            restData.add("vertices", JSON.toJsonTree(vertices(assembled)));
            restData.add("vertex_skins", JSON.toJsonTree(Arrays.copyOf(assembled.anIntArray1666, assembled.anInt1631)));
            restData.add("face_skins", JSON.toJsonTree(assembled.anIntArray1652));
            int[] faceColors = new int[assembled.anInt1628];
            for (int i = 0; i < faceColors.length; i++) faceColors[i] = assembled.aShortArray1657[i] & 65535;
            restData.add("face_colours", JSON.toJsonTree(faceColors));
            result.add("assembled_model_data", restData);
            result.add("rest_vertices", JSON.toJsonTree(restVertices));
            result.add("faces", JSON.toJsonTree(faces(rest)));
            result.add("rest_face_alphas", JSON.toJsonTree(alphas(rest)));
            for (int i = 0; i < parts.size(); i++) {
                int[][] positions = vertices(parts.get(i));
                int[] correspondence = new int[positions.length];
                Arrays.fill(correspondence, -1);
                for (int j = 0; j < positions.length; j++) {
                    for (int k = 0; k < restVertices.length; k++) {
                        if (Arrays.equals(positions[j], restVertices[k])) {
                            correspondence[j] = k;
                            break;
                        }
                    }
                }
                recipeParts.get(i).getAsJsonObject().add("assembled_vertex_indices", JSON.toJsonTree(correspondence));
            }
            result.add("parts", recipeParts);
            List<int[]> appearanceRecolors = new ArrayList<>();
            for (int color = 0; color < appearance.skin.length; color++) {
                if (appearance.skin[color] < Class47.skinCols[color].length) {
                    appearanceRecolors.add(new int[] {Class57.aShortArray465[color] & 65535,
                        Class47.skinCols[color][appearance.skin[color]] & 65535});
                }
                if (appearance.skin[color] < Looks.aShortArrayArray668[color].length) {
                    appearanceRecolors.add(new int[] {Looks.aShortArray663[color] & 65535,
                        Looks.aShortArrayArray668[color][appearance.skin[color]] & 65535});
                }
            }
            result.add("appearance_recolours", JSON.toJsonTree(appearanceRecolors));

            JsonArray poses = new JsonArray();
            JsonObject normalizedFrames = new JsonObject();
            JsonObject normalizedMaps = new JsonObject();
            for (int i = 0; i < sequence.anIntArray1262.length; i++) {
                int packed = sequence.anIntArray1262[i];
                Class104_Sub18_Sub15 group = Class34.method165(packed >>> 16);
                if (group == null) throw new IllegalStateException("Client could not load frame group " + (packed >>> 16));
                Class5 frame = group.aClass5Array1465[packed & 65535];
                Class104_Sub23 map = frame.aClass104_Sub23_23;
                normalizedFrames.add(Integer.toString(packed), JSON.toJsonTree(Map.of("map_id", map.anInt1180,
                    "indices", frame.anIntArray25, "x", frame.anIntArray26, "y", frame.anIntArray27, "z", frame.anIntArray28)));
                normalizedMaps.add(Integer.toString(map.anInt1180), JSON.toJsonTree(Map.of("types", map.anIntArray1179,
                    "labels", map.anIntArrayArray1177)));
                Class104_Sub18_Sub16_Sub4 posed = appearance.method389(sequence, i, null, 0);
                JsonObject pose = new JsonObject();
                pose.addProperty("frame_index", i);
                pose.add("vertices", JSON.toJsonTree(vertices(posed)));
                pose.add("face_alphas", JSON.toJsonTree(alphas(posed)));
                poses.add(pose);
            }
            result.add("poses", poses);
            result.add("frames", normalizedFrames);
            result.add("frame_maps", normalizedMaps);

            Player actor = new Player();
            Class75.transform(actor, sequenceId, 0);
            JsonArray clock = new JsonArray();
            int limit = Arrays.stream(sequence.anIntArray1264).sum() + 5;
            for (int tick = 0; tick <= limit; tick++) {
                clock.add(JSON.toJsonTree(Map.of("tick", tick, "sequence_id", actor.anInt1722,
                    "frame_index", actor.anInt1732, "frame_cycle", actor.anInt1724)));
                if (actor.anInt1722 == -1) break;
                Class84.method381(actor);
            }
            result.add("actor_clock", clock);
            JsonArray renderedClock = new JsonArray();
            for (int i = 1; i < clock.size(); i++) {
                JsonObject state = clock.get(i).getAsJsonObject().deepCopy();
                state.addProperty("elapsed_tick", i - 1);
                renderedClock.add(state);
            }
            result.add("rendered_actor_clock", renderedClock);
            result.addProperty("timing_origin", "after-first-logic-update");
            result.addProperty("tick_ns", Math.multiplyExact(Applet_Sub1.anInt1757, 1000000L));
            if (actor.anInt1722 != -1) throw new IllegalStateException("Attack did not finish within reference limit");
            Class104_Sub18_Sub16_Sub5 tree = new Class104_Sub18_Sub16_Sub5(models.decompress(7978, 0));
            ObjectDefinition treeDefinition = ItemDef.forId(1306);
            result.add("tree", JSON.toJsonTree(Map.of("object_id", 1306, "model_id", 7978,
                "vertices", vertices(tree), "texture_ids", tree.aShortArray1658,
                "definition_model_ids", treeDefinition.anIntArray1350, "animation_id", treeDefinition.anInt1346)));

            JsonArray textureReferences = new JsonArray();
            for (int id : new int[] {8, 34}) {
                Class104_Sub19 texture = new Class104_Sub19(new RSBuf(textures.decompress(0, id)));
                JsonObject record = new JsonObject();
                record.addProperty("id", id);
                record.addProperty("direction", texture.anInt1144);
                record.addProperty("speed", texture.anInt1137);
                record.add("sprite_ids", JSON.toJsonTree(texture.anIntArray1147));
                JsonArray samples = new JsonArray();
                for (int ticks : new int[] {0, 1, 2, 63, 64, 65}) {
                    texture.anIntArray1146 = new int[128 * 128];
                    for (int i = 0; i < texture.anIntArray1146.length; i++) texture.anIntArray1146[i] = i;
                    texture.method558(ticks);
                    samples.add(JSON.toJsonTree(Map.of("ticks", ticks, "first_pixels",
                        Arrays.copyOf(texture.anIntArray1146, 8))));
                }
                record.add("samples_128", samples);
                textureReferences.add(record);
            }
            result.add("texture_references", textureReferences);
            JsonArray resources = new JsonArray();
            for (ArchiveSource source : List.of(frames, maps, configs, models, textures)) source.record(out, resources);
            result.add("resources", resources);
            Files.writeString(out.resolve("reference.json"), JSON.toJson(canonical(result)) + "\n");
            System.out.printf("sequence=%d frames=%d vertices=%d faces=%d parts=%d resources=%d%n", sequenceId,
                poses.size(), rest.anInt1529, rest.anInt1585, parts.size(), resources.size());
        }
    }
}
