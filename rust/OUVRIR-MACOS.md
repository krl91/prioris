# Autoriser PRIORIS sur macOS

Cette archive utilise une signature ad hoc gratuite. macOS peut donc bloquer
le premier lancement parce que l'identité du développeur n'a pas été vérifiée
par Apple.

1. Double-clique sur `PRIORIS.app` une première fois. Dans un artefact de test
   qui contient seulement le binaire `prioris`, double-clique sur ce binaire.
2. Ferme le message de sécurité avec **Terminé**.
3. Ouvre **Réglages Système > Confidentialité et sécurité**.
4. Dans la section **Sécurité**, clique sur **Ouvrir quand même** à côté du
   message concernant PRIORIS.
5. Authentifie-toi si macOS le demande, puis confirme avec **Ouvrir**.

Les lancements suivants se font normalement. Pour une release publiée,
n'autorise l'application que si l'archive vient de la release officielle
PRIORIS et si son empreinte correspond à `SHA256SUMS.txt`.

## Allow PRIORIS on macOS

This archive uses free ad-hoc signing. macOS may block the first launch because
Apple has not verified the developer identity.

1. Double-click `PRIORIS.app` once. In a test artifact that contains only the
   `prioris` binary, double-click that binary instead.
2. Close the security alert with **Done**.
3. Open **System Settings > Privacy & Security**.
4. In **Security**, click **Open Anyway** next to the PRIORIS message.
5. Authenticate if requested, then confirm with **Open**.

Later launches work normally. For a published release, only approve the
application when the archive comes from the official PRIORIS release and its
checksum matches `SHA256SUMS.txt`.
