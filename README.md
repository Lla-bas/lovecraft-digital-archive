# H.P. Lovecraft Digital Archive

[![Read Online](https://img.shields.io/badge/Read%20Online-Digital%20Archive-6b3a2e)](https://lla-bas.github.io/lovecraft-corpus/)
[![Hugging Face Dataset](https://img.shields.io/badge/🤗%20Hugging%20Face-Dataset-yellow)](https://huggingface.co/datasets/Gyran/lovecraft-comprehensive-corpus)

A searchable digital archive of H.P. Lovecraft's fiction, essays, poetry, and personal correspondence, compiled into a clean reading interface and a single structured text file.

**[Open the Archive Reader →](https://lla-bas.github.io/lovecraft-corpus/)**

---

#### Archive Contents

| Category | Works | Characters |
| :--- | ---: | ---: |
| Fiction | 105 | 8,177,709 |
| Essays | 47 | 656,628 |
| Letters | 88 | 547,512 |
| Poetry | 77 | 164,351 |
| **Total** | **317** | **9,546,200** |

#### Sources

Texts are compiled and deduplicated in priority order from:

* [The H.P. Lovecraft Archive](https://hplovecraft.com)
* [Wikisource](https://en.wikisource.org/wiki/Author:Howard_Phillips_Lovecraft)
* [The LetterCraft Project](https://github.com/punchmonster/Lovecraft-Letters)

---

#### Raw Data

The complete archive is stored in [`data/lovecraft.jsonl`](data/lovecraft.jsonl) (one JSON object per line):

```json
{
  "id": "fiction/the-call-of-cthulhu",
  "category": "fiction",
  "title": "The Call of Cthulhu",
  "source": "[https://hplovecraft.com/writings/texts/fiction/cc.aspx](https://hplovecraft.com/writings/texts/fiction/cc.aspx)",
  "chars": 71342,
  "text": "..."
}
```

#### Rebuild Locally

```Bash
pip install requests beautifulsoup4
python corpus.py
```

#### Hugging Face Mirror
For research or NLP workflows, the dataset is also mirrored on Hugging Face:

```Python
from datasets import load_dataset

ds = load_dataset("Lla-bas/lovecraft-comprehensive-corpus")
```
#### License & Disclaimer
The scraper and web reader are licensed under the MIT License.

Texts are compiled for archival, research, and educational purposes. H.P. Lovecraft's works are widely considered to be in the public domain, though copyright status for certain letters or collaborative works may vary by jurisdiction. If you are a rights holder and believe any included text infringes copyright, please open an issue and it will be removed promptly.
