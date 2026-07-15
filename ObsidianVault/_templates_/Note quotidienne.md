# {{date}}

## Notes

- 
---
## Actions

- [ ]

---
## Tâches des 7 prochains jours

```dataviewjs
const currentFile = dv.current().file.name;

// Adapté à des notes nommées YYYY-MM-DD
const start = dv.date(currentFile);
const end = start.plus({ days: 7 });

const tasks = dv.pages()
    .file.tasks
    .where(t =>
        !t.completed &&
        t.due &&
        t.due >= start &&
        t.due <= end
    );

if (tasks.length === 0) {
    dv.paragraph("✅ Aucune tâche prévue sur les 7 prochains jours.");
} else {
    dv.taskList(tasks);
}
```