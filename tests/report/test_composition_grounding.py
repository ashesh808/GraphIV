"""Composition checks retain primary evidence and reject unverified prose."""

import json
from datetime import date

import pytest

from src.core.schema import Lineage, Paper
from src.miner.miner import Mined
from src.report import compose
from src.report.verify import repair_text

SOURCE_ID = "2402.19427"
OTHER_ID = "2406.07522"
SCALING_QUOTE = "Our hybrid scales to 14B parameters and matches Transformer training efficiency."
SOURCE = "Earlier recurrent models were difficult to train and scale. " * 14 + SCALING_QUOTE
OTHER_SOURCE = (
    "The bounded-state model improves efficiency on the evaluated language modeling tasks. "
    "Its citation labels are predictions and do not establish causal scientific influence."
)
SOURCES = {SOURCE_ID: SOURCE, OTHER_ID: OTHER_SOURCE}
SCALING_CLAIM = f"The evaluated hybrid scales to 14B parameters arXiv:{SOURCE_ID}."
UNSUPPORTED_DRAFT = (
    f"The hybrid failed to scale arXiv:{SOURCE_ID}. "
    "Hybrid architectures are necessary and universally best."
)


class RepairModel:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def ask(self, prompt, max_tokens=512):
        self.prompts.append(prompt)
        return self.reply


class SequenceModel(RepairModel):
    def __init__(self, replies):
        super().__init__("")
        self.replies = iter(replies)

    def ask(self, prompt, max_tokens=512):
        self.prompts.append(prompt)
        return next(self.replies)


def claim(text=SCALING_CLAIM, *, arxiv_id=SOURCE_ID, quote=SCALING_QUOTE, paragraph=0):
    return {
        "text": text,
        "paragraph": paragraph,
        "sources": [{"id": arxiv_id, "quote": quote}],
    }


def repaired(claims, *, draft=UNSUPPORTED_DRAFT, sources=None, kind="prose"):
    model = RepairModel(json.dumps({"claims": claims}))
    result = repair_text(model, draft, SOURCES if sources is None else sources, kind=kind)
    assert len(model.prompts) == 1
    return result, model.prompts[0]


def paper(arxiv_id="2402.19427", abstract="We scale the hybrid model to 14B parameters."):
    return Paper(
        arxiv_id=arxiv_id,
        title="A hybrid model with efficient scaling",
        abstract=abstract,
        date=date(2024, 2, 29),
    )


def test_digest_retains_results_after_the_former_abstract_cutoff():
    background = "Earlier recurrent models were difficult to train and scale. " * 14
    result = "Our hybrid scales to 14B parameters and matches Transformer training efficiency."
    source = paper(abstract=background + result)

    evidence = compose.digest("How well does the hybrid scale?", [source], {}, None, None, [])

    assert result in evidence
    assert source.abstract in evidence


def test_supported_replacement_uses_the_full_primary_source_tail():
    result, prompt = repaired([claim()])

    assert result == SCALING_CLAIM
    assert SOURCE in prompt
    assert UNSUPPORTED_DRAFT in prompt
    assert "failed to scale" not in result
    assert "universally best" not in result


def test_one_supported_claim_never_retains_unreviewed_draft_paragraphs():
    draft = (
        UNSUPPORTED_DRAFT
        + "\n\nThe entire field agrees that pure recurrent models cannot retrieve context."
    )
    result, _ = repaired([claim()], draft=draft)

    assert result == SCALING_CLAIM
    assert "entire field" not in result


@pytest.mark.parametrize(
    "text",
    [
        SCALING_CLAIM + " Hybrid architectures are universally necessary.",
        "## " + SCALING_CLAIM,
        "- " + SCALING_CLAIM,
        "> " + SCALING_CLAIM,
    ],
)
def test_one_source_anchor_cannot_carry_an_extra_sentence_or_unverified_heading(text):
    result, _ = repaired([claim(text=text)])

    assert result == ""


def test_a_rejected_claim_does_not_discard_or_extend_an_independent_supported_claim():
    rejected = claim(
        "Every hybrid is superior arXiv:2402.19427.",
        quote="This invented quotation does not occur in the actual supplied source.",
    )

    result, _ = repaired([claim(), rejected])

    assert result == SCALING_CLAIM
    assert "superior" not in result


@pytest.mark.parametrize("reply", ["not json", "[]", "null", "{}", '{"claims": []}'])
def test_an_unusable_repair_fails_closed_without_returning_the_original(reply):
    model = RepairModel(reply)

    assert repair_text(model, UNSUPPORTED_DRAFT, SOURCES) == ""
    assert len(model.prompts) == 1


@pytest.mark.parametrize("claims", [None, "approved", {"text": SCALING_CLAIM}, [None], ["yes"]])
def test_malformed_claim_collections_fail_closed(claims):
    result, _ = repaired(claims)

    assert result == ""


@pytest.mark.parametrize(
    "quote",
    [
        "Our hybrid scales to 13B parameters and matches Transformer training efficiency.",
        "our hybrid scales to 14B parameters and matches Transformer training efficiency.",
        "Our hybrid scales to 14B parameters, and matches Transformer training efficiency.",
        "Our hybrid",
        "",
        None,
    ],
)
def test_a_source_excerpt_must_be_nonempty_verbatim_and_bounded(quote):
    result, _ = repaired([claim(quote=quote)])

    assert result == ""


def test_whitespace_variations_in_an_exact_source_excerpt_are_accepted():
    excerpt = SCALING_QUOTE.replace(" parameters ", "\n parameters\t")
    result, _ = repaired([claim(quote=excerpt)])

    assert result == SCALING_CLAIM


def test_an_existing_excerpt_longer_than_the_limit_is_rejected():
    excerpt = "This is an actual source excerpt with deliberately excessive length. " * 16
    assert len(excerpt) > 800

    result, _ = repaired([claim(quote=excerpt)], sources={SOURCE_ID: excerpt})

    assert result == ""


def test_an_excerpt_from_another_supplied_paper_does_not_support_this_paper():
    result, _ = repaired([claim(quote=OTHER_SOURCE)])

    assert result == ""


def test_a_quote_existing_elsewhere_does_not_allow_its_source_id_to_be_swapped():
    result, _ = repaired([claim(arxiv_id=OTHER_ID)])

    assert result == ""


def test_known_but_unsupplied_paper_ids_are_not_accepted_as_evidence():
    unknown_id = "1706.03762"
    result, _ = repaired(
        [claim(text=f"This paper establishes the result arXiv:{unknown_id}.", arxiv_id=unknown_id)]
    )

    assert result == ""


@pytest.mark.parametrize(
    "text",
    [
        "The hybrid scales to 14B parameters.",
        f"The hybrid scales to 14B parameters [{SOURCE_ID}].",
        f"The hybrid scales to 14B parameters arXiv:{SOURCE_ID} and arXiv:{OTHER_ID}.",
    ],
)
def test_inline_citations_must_match_the_complete_structured_source_set(text):
    result, _ = repaired([claim(text=text)])

    assert result == ""


def test_a_multi_paper_comparison_requires_valid_quotes_from_each_cited_source():
    text = f"The papers report different evaluated results arXiv:{SOURCE_ID} and arXiv:{OTHER_ID}."
    comparison = claim(text=text)
    comparison["sources"].append({"id": OTHER_ID, "quote": OTHER_SOURCE})

    result, _ = repaired([comparison])

    assert result == text


@pytest.mark.parametrize("paragraph", [True, False, -1, 21, 0.5, "0", None])
def test_malformed_paragraph_indexes_do_not_admit_the_claim(paragraph):
    result, _ = repaired([claim(paragraph=paragraph)])

    assert result == ""


@pytest.mark.parametrize(
    "changes",
    [
        {"text": None},
        {"text": ""},
        {"text": 17},
        {"sources": []},
        {"sources": None},
        {"sources": {"id": SOURCE_ID, "quote": SCALING_QUOTE}},
        {"sources": [None]},
        {"sources": [{"id": SOURCE_ID}]},
    ],
)
def test_incomplete_structured_claims_cannot_retain_unverified_prose(changes):
    proposed = claim() | changes
    result, _ = repaired([proposed])

    assert result == ""


def test_valid_claims_keep_model_order_and_separate_contiguous_paragraph_groups():
    first = claim(paragraph=0)
    second_text = f"The model matches training efficiency arXiv:{SOURCE_ID}."
    second = claim(text=second_text, paragraph=0)
    third_text = f"The second paper evaluates a bounded-state model arXiv:{OTHER_ID}."
    third = claim(text=third_text, arxiv_id=OTHER_ID, quote=OTHER_SOURCE, paragraph=1)

    result, _ = repaired([first, second, third])
    paragraphs = result.split("\n\n")

    assert len(paragraphs) == 2
    assert paragraphs[0].startswith(SCALING_CLAIM)
    assert paragraphs[0].endswith(second_text)
    assert paragraphs[1] == third_text


def test_a_citation_walk_is_not_kept_as_causal_proof_when_no_supported_claim_is_returned():
    causal_draft = (
        f"The citation walk proves that arXiv:{SOURCE_ID} caused arXiv:{OTHER_ID} to adopt "
        "its architecture, and independently reproduces the model's experimental results."
    )

    result, prompt = repaired([], draft=causal_draft, kind="lineage description")

    assert result == ""
    assert SOURCE in prompt and OTHER_SOURCE in prompt
    assert causal_draft in prompt


def test_an_open_question_can_use_its_original_fulltext_section_tail():
    section = (
        "We discuss the evaluated experiments and their implementation. " * 36
        + "An open issue is whether the kernel remains stable under reduced precision."
    )
    quote = "An open issue is whether the kernel remains stable under reduced precision."
    question = f"Can kernel stability be retained at lower precision arXiv:{SOURCE_ID}?"

    result, prompt = repaired(
        [claim(text=question, quote=quote)],
        draft=question,
        sources={SOURCE_ID: section},
        kind="open questions",
    )

    assert result == question
    assert section in prompt


def test_answer_repairs_against_original_abstracts_instead_of_its_generated_evidence():
    generated_evidence = "All hybrid architectures are necessary and universally best."
    model = SequenceModel([UNSUPPORTED_DRAFT, json.dumps({"claims": [claim()]})])

    result = compose.answer(
        model,
        "How well does the hybrid scale?",
        date(2026, 11, 2),
        generated_evidence,
        papers=[paper(abstract=SOURCE)],
    )

    assert result == SCALING_CLAIM
    assert len(model.prompts) == 2
    assert SOURCE in model.prompts[1]
    assert generated_evidence not in model.prompts[1]


def test_answer_without_original_sources_does_not_return_unverified_generation():
    model = RepairModel(UNSUPPORTED_DRAFT)

    result = compose.answer(model, "A question", date(2026, 11, 2), UNSUPPORTED_DRAFT)

    assert result == ""
    assert len(model.prompts) == 1


def test_unanswered_passes_complete_original_sections_to_generation_and_repair():
    quote = "An open issue is whether the kernel remains stable under reduced precision."
    section = "Here we discuss the implementation of our evaluated model. " * 36 + quote
    question = f"Can kernel stability be retained at lower precision arXiv:{SOURCE_ID}?"
    model = SequenceModel(
        [
            json.dumps({"open": [question]}),
            json.dumps({"claims": [claim(text=question, quote=quote)]}),
        ]
    )

    result = compose.unanswered(model, "What remains open?", [(SOURCE_ID, "Limitations", section)])

    assert result == [question]
    assert len(model.prompts) == 2
    assert all(section in prompt for prompt in model.prompts)


def test_lineage_description_cannot_fall_back_to_unsupported_causal_prose():
    source = paper(abstract=SOURCE)
    causal = "This path proves the first model caused all subsequent architectures."
    model = SequenceModel(
        [json.dumps({"name": "Efficient hybrid models", "description": causal}), '{"claims":[]}']
    )
    found = Mined(papers={SOURCE_ID: source}, lineages=[Lineage(nodes=[SOURCE_ID])])

    result = compose.name_line(model, "Which work is connected?", found, [SOURCE_ID], [])

    assert causal not in result.description
    assert "does not establish" in result.description
    assert len(model.prompts) == 2
    assert all(SOURCE in prompt for prompt in model.prompts)


def test_compose_repairs_each_section_and_drops_an_unsupported_opening(monkeypatch):
    title = "Scaling under the evaluated training setup"
    monkeypatch.setattr(
        compose,
        "outline",
        lambda *_args: [(title, [SOURCE_ID], "Describe the reported scaling experiment.")],
    )
    opening = "The entire field agrees all pure recurrent architectures are obsolete."

    class SectionModel(RepairModel):
        def ask_many(self, prompts, max_tokens=512):
            assert all(SOURCE in prompt for prompt in prompts)
            return [UNSUPPORTED_DRAFT]

        def ask(self, prompt, max_tokens=512):
            self.prompts.append(prompt)
            if "UNTRUSTED DRAFT:" not in prompt:
                return opening
            assert SOURCE in prompt
            claims = [] if opening in prompt else [claim()]
            return json.dumps({"claims": claims})

    model = SectionModel("")

    result = compose.compose(
        model,
        "How well does the hybrid scale?",
        date(2026, 11, 2),
        [paper(abstract=SOURCE)],
        {},
        None,
        None,
        [],
    )

    assert len(result) == 1
    assert result[0].title == "Evidence: A hybrid model with efficient scaling"
    assert result[0].body == SCALING_CLAIM
    assert len(model.prompts) == 3


def test_unsupported_outline_headings_and_unknown_source_ids_do_not_escape():
    heading = "Hybrid Models Are Necessary and Universally Best"
    unknown_id = "1706.03762"
    plan = {
        "sections": [
            {"title": heading, "ids": [unknown_id, SOURCE_ID], "point": "An unsupported claim."},
            {"title": "An unavailable paper proves more", "ids": [unknown_id], "point": "More."},
        ]
    }

    class OutlineModel(RepairModel):
        def ask_many(self, prompts, max_tokens=512):
            assert len(prompts) == 1
            assert f"It must discuss these papers: {SOURCE_ID}" in prompts[0]
            assert unknown_id not in prompts[0]
            return [f"## {heading}\n{UNSUPPORTED_DRAFT}"]

        def ask(self, prompt, max_tokens=512):
            if "Plan the sections of a literature review" in prompt:
                return json.dumps(plan)
            if "UNTRUSTED DRAFT:" in prompt:
                return json.dumps({"claims": [claim()]})
            return ""

    result = compose.compose(
        OutlineModel(""),
        "How well does the hybrid scale?",
        date(2026, 11, 2),
        [paper(abstract=SOURCE)],
        {},
        None,
        None,
        [],
    )

    assert len(result) == 1
    assert result[0].title == "Evidence: A hybrid model with efficient scaling"
    assert result[0].body == SCALING_CLAIM
    assert heading not in str(result)
    assert unknown_id not in str(result)


def test_unsupported_causal_lineage_names_are_replaced_with_source_metadata():
    first = paper(abstract=SOURCE).model_copy(update={"title": "Recurrent scaling"})
    last = paper(arxiv_id=OTHER_ID, abstract=OTHER_SOURCE).model_copy(
        update={"title": "Bounded-state models"}
    )
    heading = "The First Model Caused and Proved All Later Architectures"
    model = SequenceModel(
        [
            json.dumps({"name": heading, "description": UNSUPPORTED_DRAFT}),
            '{"claims":[]}',
        ]
    )
    found = Mined(papers={SOURCE_ID: first, OTHER_ID: last})

    result = compose.name_line(model, "Which work is connected?", found, [SOURCE_ID, OTHER_ID], [])

    assert result.name == "Citation path: Recurrent scaling / Bounded-state models"
    assert heading not in str(result)
    assert UNSUPPORTED_DRAFT not in result.description
    assert "does not establish methodological ancestry or influence" in result.description
