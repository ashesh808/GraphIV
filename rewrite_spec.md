can we design this to be more simple. like think of this right, this is becoming a huge codebase and you are a fuck boner for complexity which is a retarded concept. We wanted it clean and managable. Quit whatever exists now and let's formulate a redesign, small steps at a time. I am a human and I can ingest a finite number of information so stop info dumping shit you fuckass. 

I wanted: two clear stage first. A stage that CREATES the postgres, and the stage that USES the postgres. Download, embed, cluster, should be the stage that CREATES the postgres and this is no longer questioned. My mental model is as follows: a JSON acts as source of truth obtained from kaggle or some metadata provider, then we expect something like PG_DEST to be where the table is. There will be two tables in the db

PAPERS: arxiv_id, stage, title, abstract, date, primary_category, authors, embed_full, embed_umap, level_0, level_1, level_2 -> create INDEX (arxiv_id, stage), create INDEX (level_0, level_1, level_2)
CITATIONS: citation_id, source_id, target_id, stage, section, resolved_by, sentence, intent, intent_score

one row per paper, so everything about a paper is in one place and there is nothing to keep in sync
citations are separate because they are one row per edge, not per paper
re-embedding or re-clustering is a 3.1M row UPDATE which doubles the table on disk, so follow it with a VACUUM FULL

We read from PG_DEST's PAPERS table in the "stages" column. The stages: just added from json (0), download_pdf (1), download_html (2), embed_paper (3), create_topic_tree (4)

configs
```toml
[database]
PG_DEST = XXXX

[source]
SOURCE_URL = XXXX
SOURCE_PATH = "XXXXX/YYY.json" (the file grabbed)
PDF_BASE_URL = XXXX
HTML_BASE_URL

[dataset]
PDF_PATH = XXXX
HTML_PATH = XXXX

[download]
PDF_BATCH = int
PDF_N_PARALLEL = int
HTML_BATCH = int

[endpoints]
EMBED_API = XXXXX:PORT
EMBED_NAME = "nomic" whatever
EMBED_PARALLEL = 4
LLM_API = XXXXX:PORT
LLM_NAME = "gemma" whatever
LLM_PARALLEL = 4

[umap]
UMAP_MODEL_PATH = XXXX
UMAP_SAMPLE = int
UMAP_DIM = 50

[topics]
TREE_METHODS = ["kmeans", "kmeans", "hdbscan"]
TREE_K = 16 (k for the kmeans levels)
TREE_MIN_CLUSTER_SIZE = int (for the hdbscan levels)
TREE_BATCH = int

[citation_labeler]
LABELER_PATH = XXXX (data/citation_labeler here)
LABELER_BATCH = int
LABELER_APE_MODEL = "gemma" whatever
LABELER_APE_GENERATIONS = 6
LABELER_APE_PARALLEL = 4
LABELER_TEACHER_SAMPLE = 10000
LABELER_SEED = 0
LABELER_SPLITS = [0.8, 0.1, 0.1] (train, val, test)
LABELER_EPOCHS = 4
LABELER_TRAIN_BATCH = 64
LABELER_LR = float
```

new data dir
```
data/
    pdf/
    html/
    pg/
    citation_labeler/
        ground_truth.csv (the ~1000 reference rows, columns sentence and label)
        teacher_labeled.csv
        best.txt (the winning prompt)
        prompts/
            prompt_XX.txt (00 is the seed you write by hand, then 01 02 03 for generations)
        ckpts/
            iteration_XX.pt (one per epoch)
        best.pt (the winning student)
        logs/
            teacher_matrix.png
            student_matrix.png
            class_distribution.png
            student.log
```

(goal: to create a finished PAPERS table) files: all in `scripts/papers_preprocess/` with a readme.md explain in 1 short sentence what each file does, something like 

```
`stage0_fetch_source_json.py`: fetches a new source metadata from kaggle
```

`stage0_fetch_source_json.py`: class SourceFetcher that takes source_path: str and source_url: str as __init__ input.
Methods
`def fetch_url()` downloads the new json at url to a temporary path (take source_path and just do .temp after it)
`def fetch_and_replace()` calls `fetch_url()` first, reads the two jsons, the new and the old, compare the date of the latest paper in both. If the new one has newer papers, then the new one replaces the old
`def update_db(PG_DEST)` calls `fetch_and_replace()` and grab all available arxiv_id, then queries from the PAPERS table at the dest to grab all arxiv_id NOT in the table. 
Initialize them with arxiv_id, stage=0, and title, absract, date, primary_category, authors, from the source json, and the rest as NULL for now
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `update_db()`

`stage1_download_pdf.py`: class PDFDownloader, takes path and base_url as init, initialize self.download_set as empty set
(set, so unique)
Methods
`def create_queue(PG_DEST)` queries from the PAPAERS table all row with stage 0, add resulting id to download_set
`def download(PG_DEST, batch, parallel)` performs downloads like we currently do
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `download()`

`stage2_download_html.py` class HTMLDownloader, same idea but query with stage 1 and do the HTML instead with different methods to handle the html batch dl

`stage3_embed_papers.py` class Embedder expects base_url and embedder_name as __init__
`def embed(abstract: str) -> whatever type embedding returns` embeds the abstract from base_url using embedder_name
`def embed_to_db(PG_DEST, batch)` queries from PAPERS at PG_DEST where stage=2, for each one, grab the abstract, call embedder, then perform the embedding at batch, populates embed_full, sets stage=3
`def fit_umap(PG_DEST, sample, path)` takes `sample` random rows of embed_full, fits umap once, saves the fitted model to path, does nothing if the file already exists
`def umap_to_db(PG_DEST, batch, path)` loads the fitted model from path, queries PAPERS where embed_full IS NOT NULL and embed_umap IS NULL, transforms embed_full at batch, populates embed_umap
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `embed_to_db()` then `fit_umap()` then `umap_to_db()`

`stage4_create_topic_tree.py` class TopicTree expects k: int and min_cluster_size: int as __init__
methods is the clustering method to use at each level, in order, so ["kmeans", "kmeans", "hdbscan"] means kmeans for level_0, kmeans for level_1, hdbscan for level_2
len(methods) is the depth of the tree, and PAPERS has three level columns, so the list is length 3 until you add a level_3 column
Methods
`def cluster_one(vecs, method) -> list[int]` runs the named method on vecs and returns one label per row, kmeans uses self.k, hdbscan uses self.min_cluster_size and labels noise -1
`def cluster(PG_DEST, methods, batch)` reads arxiv_id and embed_umap from PAPERS where stage=3, calls `cluster_one()` with methods[0] on all of them to get level_0, then for each level_0 group calls `cluster_one()` with methods[1] on just that group to get level_1, then for each level_1 group calls `cluster_one()` with methods[2] on just that group to get level_2, writes level_0, level_1, level_2 back at batch, sets stage=4
`main()` simply reads from config.toml (or expect --config_path), reads TREE_METHODS as the methods list, pass the right vars, calls `cluster()`

(goal: to create a finished CITATIONS table, expects a finished PAPERS table at stage 4, so this runs after the main stuff is done, and a best.pt from the citation_labeler) files: all in `scripts/citation_preprocess/` with a readme.md explain in 1 short sentence what each file does

`stage0_create_citation.py` init takes html_path
basemodel citation smth smth define here
```
class Citation
(section, sentence, resolved_by)
```
`def extract_citations(arxiv_id)` reads the html from path and fills the ctation types, returns list of `Citation`. this is where the current method resolutions gets ported to `resolved_by`
`def populate_citation_table(PG_DEST)` read the PAPERS table, find all arxiv_id not in the source_id col of the CITATIONS table. perform `extract_citations()` on them and populate, then set stage to 0 for each
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `populate_citation_table()`

`stage1_label_citation.py` init takes labeler_path, initializes self.model by loading best.pt to the model's weight
`def label_one(sentence)` labels once, return intent
`def label(PG_DEST, batch, relabel)` labels in batches, normally only the rows where intent IS NULL, with relabel it does every row in the table instead
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `label()`, takes --relabel to redo the whole table after a new best.pt lands

(goal: populate the data/citation_labeler dir, ending in best.pt) files: all in `scripts/citation_labeler/` with a readme.md explain in 1 short sentence what each file does

this whole dir is asynchronous, run it when you want a better labeler, everything else only ever reads best.pt
ground_truth.csv is stratified six ways and built by agreement, not by hand: two retired students and the teacher label the same citations and only unanimous rows survive, so it stands in for a human. Nothing in this directory writes it

`stage0_ape_prompt.py` class PromptRefiner expects model: str and generations: int as __init__
Methods
`def label(prompt, rows)` runs the prompt over rows, returns one predicted intent each
`def critique(prompt, wrong)` shows the judge the mistakes, returns what the prompt got wrong
`def redraft(prompt, notes)` rewrites the prompt from the critique
`def refine(labeler_path)` seeds from prompts/prompt_00.txt, reads ground_truth.csv, loops label then critique then redraft for generations, writes each one to prompts/prompt_XX.txt, writes the one with the best accuracy on ground_truth.csv to best.txt
`def report(labeler_path)` scores best.txt against ground_truth.csv, writes the confusion matrix to logs/teacher_matrix.png
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `refine()` then `report()`

`stage1_teacher_label.py` class Teacher expects model: str and prompt_path: str as __init__
`def label_one(section, sentence)` runs best.txt on one citation, returns intent and intent_score
`def label(PG_DEST, sample, batch)` takes `sample` rows from the CITATIONS table, calls `label_one()` on each at batch, writes teacher_labeled.csv
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `label()`

`stage2_train_student.py` class Student expects labeler_path: str, seed: int and splits: tuple as __init__
`def load()` reads teacher_labeled.csv, splits it into train, val and test with seed
`def train(epochs, batch, lr)` finetunes distilbert on train, checks val at the end of every epoch, writes ckpts/iteration_XX.pt each time, copies the best val epoch to best.pt
`def report()` scores best.pt on test and on ground_truth.csv, writes the confusion matrix to logs/student_matrix.png, writes the intent counts of teacher_labeled.csv to logs/class_distribution.png, writes the whole run to logs/student.log
`main()` simply reads from config.toml (or expect --config_path), pass the right vars, calls `load()` then `train()` then `report()`

the XX in prompts/ and the XX in ckpts/ are unrelated, one is a generation and the other is an epoch
