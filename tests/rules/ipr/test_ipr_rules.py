import pytest
from core.engine.runner import load_rule, run_rule
from core.schemas import AnalysisInput

RULE_PATH = "contract_review_app/legal_rules/policy_packs/ipr_core.yaml"
AI = lambda text: AnalysisInput(text=text, clause_type="ipr")

def _run(text, rule_id):
    rule = load_rule(RULE_PATH, rule_id=rule_id)
    return run_rule(rule, AI(text))

# R1 Agreement Documentation title

def test_agreement_docs_title_pass():
    txt = "Title to the Agreement Documentation shall vest in Company upon creation."
    res = _run(txt, "ipr.agreement_docs_title.company")
    assert res and any("Company" in f.message for f in res.findings)


def test_agreement_docs_title_fail():
    txt = "Title to the Agreement Documentation shall remain with the Contractor and be assigned later."
    res = _run(txt, "ipr.agreement_docs_title.company")
    assert res and any("сохраняется" in f.message for f in res.findings)

# R2 Foreground IPR licence

def test_fg_licence_scope_pass():
    txt = (
        "Company is granted a worldwide, royalty-free, perpetual, irrevocable, transferable and "
        "sublicensable licence to modify Foreground IPR. All modifications shall vest in Company."
    )
    res = _run(txt, "ipr.fg.licence.scope")
    assert res and any("присутствует" in f.message for f in res.findings)


def test_fg_licence_scope_fail_missing_transferable():
    txt = (
        "Company is granted a worldwide, royalty-free, perpetual, irrevocable and sublicensable "
        "licence to modify Foreground IPR. All modifications shall vest in Company."
    )
    res = _run(txt, "ipr.fg.licence.scope")
    assert res and any("не покрывает" in f.message for f in res.findings)

# R3 Background IPR term conflict

def test_bg_licence_conflict_fail():
    txt = (
        "Contractor grants a perpetual, irrevocable licence to its Background IPR, provided that such licence is only for the duration of the Agreement."
    )
    res = _run(txt, "ipr.bg.licence.conflict")
    assert res and any("конфликт" in f.message.lower() for f in res.findings)


def test_bg_licence_conflict_ok():
    txt = "Contractor grants a perpetual, irrevocable licence to its Background IPR."
    res = _run(txt, "ipr.bg.licence.conflict")
    assert res is None

# R4 Moral rights waivers

def test_moral_rights_waiver_fail():
    txt = "Contractor's personnel retain all moral rights in the Works."
    res = _run(txt, "ipr.moral_rights.waiver")
    assert res and any("отсутствует" in f.message.lower() for f in res.findings)


def test_moral_rights_waiver_pass():
    txt = "The Contractor's personnel irrevocably and unconditionally waive all moral rights in the Works."
    res = _run(txt, "ipr.moral_rights.waiver")
    assert res is None

# R5 IPR indemnity remedies

def test_indemnity_remedies_fail():
    txt = "Contractor shall indemnify Company for any IPR claim and may replace the item at its option."
    res = _run(txt, "ipr.indemnity.remedies")
    assert res and any("неполные" in f.message for f in res.findings)


def test_indemnity_remedies_pass():
    txt = (
        "Contractor shall indemnify Company for any IPR claim and shall procure a licence or replace or modify the infringing item to provide equivalent performance at no additional cost and no adverse impact on other works or interfaces, subject to this Agreement."
    )
    res = _run(txt, "ipr.indemnity.remedies")
    assert res is None

# R6 Brand use prohibition

def test_brand_use_prohibition_fail():
    txt = "Contractor may use the Company's name and logo for marketing unless the Company objects."
    res = _run(txt, "ipr.brand.use.prohibition")
    assert res and any("бренда" in f.message.lower() for f in res.findings)


def test_brand_use_prohibition_pass():
    txt = "Contractor shall not use the Company's name or logo without the Company's prior written consent."
    res = _run(txt, "ipr.brand.use.prohibition")
    assert res is None

# R7 Supplied Software definition

def test_supplied_software_definition_warn():
    txt = "Supplied Software includes software and manuals."
    res = _run(txt, "ipr.supplied_software.definition")
    assert res and any("неполное" in f.message for f in res.findings)


def test_supplied_software_definition_ok():
    txt = (
        "Supplied Software includes software, embedded firmware, activation keys, test scripts, patches and updates, and manuals."
    )
    res = _run(txt, "ipr.supplied_software.definition")
    assert res is None

# R8 Further assurances / PoA

def test_further_assurances_poa_warn():
    txt = "Contractor assigns intellectual property rights to Company."
    res = _run(txt, "ipr.further_assurances.poa")
    assert res and any("Отсутствует" in f.message for f in res.findings)


def test_further_assurances_poa_ok():
    txt = "Contractor shall execute further assurances to perfect rights and grants an irrevocable power of attorney to the Company to do so."
    res = _run(txt, "ipr.further_assurances.poa")
    assert res is None

# R9 OSS guardrails

def test_oss_guardrails_warn():
    txt = "Supplier shall deliver the software in executable form."
    res = _run(txt, "ipr.oss.guardrails")
    assert res and any("OSS" in f.message for f in res.findings)


def test_oss_guardrails_ok():
    txt = "Supplier shall comply with the Company's open source policy, provide an SBOM, and avoid any copyleft software."
    res = _run(txt, "ipr.oss.guardrails")
    assert res is None

# R10 Source code escrow

def test_source_code_escrow_warn():
    txt = "The Contractor shall provide the source code of critical software to the Company."
    res = _run(txt, "ipr.source_code.escrow")
    assert res and any("escrow" in f.message.lower() for f in res.findings)


def test_source_code_escrow_ok():
    txt = "For critical software the source code shall be deposited with an escrow agent, to be released on bankruptcy, failure to support or breach."
    res = _run(txt, "ipr.source_code.escrow")
    assert res is None
