# Unparsed teacher answers

## Question

Why 10 to 20% of citations came back with no usable label, and whether it was the parser, the
prompt, the token budget or the server.

## Configuration

| item | value |
| --- | --- |
| rows | 985 from `ground_truth.csv` |
| batches | 40 of 25, 4 concurrent, matching the stage |
| prompt | `best.txt` |
| model | Gemma-4-26B-Batched via llama-router |
| max_tokens | `25 * 48 + 256 = 1456` |

## What the failures are

| finish_reason | content | reasoning_content | batches | items | unparsed |
| --- | --- | --- | --- | --- | --- |
| stop | text | none | 35 | 860 | 0 |
| length | text | none | 1 | 25 | 0 |
| length | empty | present | 4 | 100 | 100 |

Failure is all-or-nothing per call, never partial. The four failing batches carry a full
`reasoning_content` and an empty `content`: the model works the items one by one inside its
thinking channel, reaches the token cap, and never emits the answer.

## The fix

| | unparsed | empty content | thinking | hit the cap | completion tokens |
| --- | --- | --- | --- | --- | --- |
| as shipped | 100/985 | 4/40 | 4/40 | 5/40 | 23,698 |
| `reasoning_effort: "none"` | 0/985 | 0/40 | 0/40 | 0/40 | 17,177 |

## Things ruled out

| candidate | evidence against |
| --- | --- |
| the parser | both answer shapes parse; 35 of 40 batches came back 0/25 unparsed |
| the token budget | raising 48 to 128 per item changed nothing, the runaway fills whatever cap it is given |
| router eviction under `MAX_MODELS_PER_GPU: 1` | the failing calls carry a complete `reasoning_content`, so the model was loaded and generating throughout |
| particular content | the same batch parses cleanly on a repeat; failures move between batches across runs |

## Files

| file | holds |
| --- | --- |
| `capture.py` | one full pass, keeping every raw completion |
| `responses.jsonl` | the 40 records as shipped |
| `responses_noreason.jsonl` | the 40 records with reasoning disabled |
