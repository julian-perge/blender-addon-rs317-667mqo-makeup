import java.io.InputStream;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.FieldVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

// Prints one TSV row per class, field and method that carries @ObfuscatedName:
// kind, obfuscated class, obfuscated member, descriptor, current (mapped) name.
public class Dump {
    static final String OBF = "Lnet/runelite/mapping/ObfuscatedName;";

    static String[] holder() { return new String[1]; }

    static AnnotationVisitor capture(String desc, String[] out) {
        if (!OBF.equals(desc)) return null;
        return new AnnotationVisitor(Opcodes.ASM5) {
            @Override public void visit(String name, Object value) { out[0] = (String) value; }
        };
    }

    public static void main(String[] args) throws Exception {
        System.out.println("kind\tobf_class\tobf_member\tdescriptor\tname");
        try (JarFile jar = new JarFile(args[0])) {
            for (Enumeration<JarEntry> e = jar.entries(); e.hasMoreElements();) {
                JarEntry entry = e.nextElement();
                if (!entry.getName().endsWith(".class") || entry.getName().contains("/")) continue;
                try (InputStream in = jar.getInputStream(entry)) {
                    String[] cls = holder();
                    String[] clsName = holder();
                    StringBuilder rows = new StringBuilder();
                    new ClassReader(in).accept(new ClassVisitor(Opcodes.ASM5) {
                        @Override public void visit(int v, int a, String name, String s, String sup, String[] i) { clsName[0] = name; }
                        @Override public AnnotationVisitor visitAnnotation(String desc, boolean vis) { return capture(desc, cls); }
                        @Override public FieldVisitor visitField(int a, String name, String desc, String s, Object v) {
                            String[] obf = holder();
                            return new FieldVisitor(Opcodes.ASM5) {
                                @Override public AnnotationVisitor visitAnnotation(String d, boolean vis) { return capture(d, obf); }
                                @Override public void visitEnd() { if (obf[0] != null) rows.append("field\t%s\t" + obf[0] + "\t" + desc + "\t" + name + "\n"); }
                            };
                        }
                        @Override public MethodVisitor visitMethod(int a, String name, String desc, String s, String[] ex) {
                            String[] obf = holder();
                            return new MethodVisitor(Opcodes.ASM5) {
                                @Override public AnnotationVisitor visitAnnotation(String d, boolean vis) { return capture(d, obf); }
                                @Override public void visitEnd() { if (obf[0] != null) rows.append("method\t%s\t" + obf[0] + "\t" + desc + "\t" + name + "\n"); }
                            };
                        }
                    }, ClassReader.SKIP_CODE);
                    String c = cls[0] == null ? "?" : cls[0];
                    System.out.println("class\t" + c + "\t\t\t" + clsName[0]);
                    System.out.print(rows.toString().replace("%s", c));
                }
            }
        }
    }
}
