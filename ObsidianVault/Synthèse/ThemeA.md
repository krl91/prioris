
```dataviewjs
const tag = "#sujet/" +
    dv.current().file.name
        .toLowerCase()
        .replace(/\s+/g, "");

const pages = dv.pages(tag);

const titre = tag.split("/").pop();
const nom = titre.charAt(0).toUpperCase() + titre.slice(1);

const results = [];

for (const page of pages) {

    const content = await dv.io.load(page.file.path);
    if (!content) continue;

    const lines = content.split("\n");

    for (let i = 0; i < lines.length; i++) {

        const line = lines[i];

        if (!line.includes(tag)) continue;

        // Ignorer les tâches
        if (/^\s*[-*]\s*\[[ xX]\]/.test(line)) {
            continue;
        }

        let block = [];

        block.push(
            line
                .replace(/^[-*]\s*/, "")
                .replace(tag, "")
                .replace(/^:\s*/, "")
                .trim()
        );

        let j = i + 1;

        while (j < lines.length) {

            const childLine = lines[j];

            // Arrêt sur un nouveau point de même niveau
            if (
                childLine.match(/^[-*]\s/) &&
                !childLine.startsWith("\t") &&
                !childLine.startsWith("    ")
            ) {
                break;
            }

            // Ignorer les lignes vides
            if (childLine.trim() !== "") {
                block.push(childLine.trim());
            }

            j++;
        }

        results.push({
            file: page.file.link,
            name: page.file.name,
            text: block
                .map((line, index) =>
                    index === 0
                        ? line
                        : `&nbsp;&nbsp;&nbsp;&nbsp;${line}`
                )
                .join("<br>")
        });
    }
}

results.sort((a, b) => b.name.localeCompare(a.name));

dv.header(2, `Liste des points traitant de ${nom}`);

if (results.length === 0) {

    dv.paragraph(`⚠️ Aucun point trouvé pour ${tag}`);

} else {

    dv.table(
        ["Jour", "Information"],
        results.map(result => [
            result.file,
            result.text
        ])
    );
}
```

## Tâches
```tasks

tag includes #sujet/themea

sort by status

```
