import random
from schema import SensorReading
from utils.risk_model import graduated_risk

def test_structural_hard_gate_zero_false_escalation():
    """
    Generate 500 random scenarios where baseline hazards are absent
    (gas <= 10, oxygen between 19.5 and 23.5, no hazardous permits).
    Assert that the severity never escalates beyond NOMINAL (score < 20),
    even if temperature, humidity, and worker counts are very high.
    """
    for _ in range(500):
        # Generate safe baseline
        gas = random.uniform(0, 10.0)
        oxy = random.uniform(19.5, 23.5)
        
        # Generate extreme environmental factors
        temp = random.uniform(10.0, 50.0)
        hum = random.uniform(20.0, 100.0)
        workers = random.randint(0, 20)
        
        reading = SensorReading(
            zone="Zone-A-Test",
            timestamp="2026-07-19T14:00:00Z",
            gas_ppm=gas,
            oxygen_pct=oxy,
            temp_c=temp,
            humidity_pct=hum,
            worker_count=workers,
            permit_type=None
        )
        
        # We can add non-hazardous permits like "general" or "inspection"
        safe_permits = random.choice([[], ["general"], ["inspection"]])
        
        result = graduated_risk(reading, safe_permits)
        assert result["score"] < 20, f"False escalation detected! Score: {result['score']}, factors: {result['contributions']}"
        assert result["band"] == "NOMINAL"
