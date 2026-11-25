package org.monapp.gestionbudget;

import android.os.Bundle;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import org.kivy.android.PythonActivity;

/** Save the legacy SQLite files before the bootstrap refreshes its app directory. */
public class BudgetActivity extends PythonActivity {
    @Override
    public void onCreate(Bundle state) {
        try {
            preserveLegacyDatabase();
        } catch (IOException error) {
            throw new IllegalStateException("Impossible de conserver l’ancienne base de budget.", error);
        }
        super.onCreate(state);
    }

    private void preserveLegacyDatabase() throws IOException {
        File files = getFilesDir();
        File old = new File(files, "app/budget.db");
        File snapshot = new File(files, "budget-migration");
        if (new File(files, "budget.db").exists() || snapshot.exists() || !old.isFile()) {
            return;
        }
        File staging = new File(files, "budget-migration.tmp");
        if (!staging.isDirectory() && !staging.mkdir()) {
            throw new IOException("Création du dossier temporaire impossible");
        }
        for (String suffix : new String[]{"", "-journal", "-wal"}) {
            File source = new File(old.getPath() + suffix);
            File target = new File(staging, "budget.db" + suffix);
            if (!source.exists()) {
                if (target.exists() && !target.delete()) {
                    throw new IOException("Ancienne copie temporaire inaccessible");
                }
                continue;
            }
            try (FileInputStream in = new FileInputStream(source);
                 FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[65536];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    out.write(buffer, 0, n);
                }
                out.getFD().sync();
            }
        }
        if (!staging.renameTo(snapshot)) {
            throw new IOException("Enregistrement de la copie impossible");
        }
    }
}

