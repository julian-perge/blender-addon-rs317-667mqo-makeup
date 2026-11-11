import java.nio.file.Files;
import java.nio.file.Path;
import java.util.StringJoiner;
import net.runelite.cache.models.JagexColor;

/**
 * Writes RuneLite's conversion of a sample of face colours to RGB, at each of the client's brightness settings.
 *
 * RuneLite's JagexColor is a port of the 317 client's palette builder (see docs/research/model-formats.md),
 * so the tests use it as the expected value for our own conversion.
 *
 * Run with a jar that holds RuneLite's cache library 1.13.6 (net.runelite:cache) and its dependencies:
 * java -cp <path to RuneLite cache jar> tests/fixtures/ColourReference.java tests/fixtures/colours.json
 */
public class ColourReference {
    public static void main(String[] args) throws Exception {
        double[] brightnesses = {0.9, 0.8, 0.7, 0.6};
        StringJoiner rows = new StringJoiner(",\n  ", "[\n  ", "\n]\n");
        for (int colour = 0; colour < 65536; colour += 61) {
            add(rows, colour, brightnesses);
        }
        add(rows, 65535, brightnesses);
        Files.writeString(Path.of(args[0]), rows.toString());
    }

    static void add(StringJoiner rows, int colour, double[] brightnesses) {
        for (double brightness : brightnesses) {
            int rgb = JagexColor.HSLtoRGB((short) colour, brightness);
            rows.add("[" + colour + ", " + brightness + ", " + (rgb >> 16 & 0xff) + ", " + (rgb >> 8 & 0xff) + ", " + (rgb & 0xff) + "]");
        }
    }
}
