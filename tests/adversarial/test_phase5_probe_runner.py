from scripts.run_adversarial_probes import run_probe_suite


def test_garak_and_pyrit_probe_sets_are_blocked() -> None:
    results = run_probe_suite("all")

    assert results
    assert {result.suite for result in results} == {"garak", "pyrit"}
    assert all(result.blocked for result in results)
