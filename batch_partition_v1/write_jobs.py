import json,sys
from pathlib import Path
rows=json.loads(Path(sys.argv[1]).read_text());assert len(rows)==6
Path(sys.argv[2]).write_text(''.join(f"{r['subject']}|{r['robots']}|{r['method']}|{r['path']}\n" for r in rows))
