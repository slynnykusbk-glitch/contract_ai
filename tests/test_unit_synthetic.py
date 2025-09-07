from src.risk_indemnities_analyzer import analyze

def test_negative_no_consequential_loss():
    t = "This contract has no such definition and no carveouts and no defend phrase."
    r = analyze(text=t)["risk_indemnities"]
    assert r["consequential_loss_defined"]["present"] is False
    assert r["indemnify_defend_hold_harmless"]["present"] is False

def test_positive_defence_and_carveouts():
    t = ("Indemnify means defend, indemnify, release, and hold harmless. "
         "Consequential Loss means loss of profit, loss of production, loss of use, "
         "loss or deferment of revenue, loss of business opportunity or goodwill. "
         "Consequential Loss does not include liquidated damages or defence costs.")
    r = analyze(text=t)["risk_indemnities"]
    assert r["indemnify_defend_hold_harmless"]["present"] is True
    assert r["consequential_loss_defined"]["present"] is True
    assert r["consequential_loss_carveouts_present"]["present"] is True
