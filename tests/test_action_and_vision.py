import os
import pytest
import numpy as np

def test_action_agent_offline_fallback():
    from agents.action_agent import ActionAgent
    
    # Temporarily remove GEMINI_API_KEY to force offline mode
    original_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = ""
    
    try:
        agent = ActionAgent()
        
        # Test safe condition
        res_safe = agent.decide_and_act("Zone-A", 40.0, 15.0)
        assert res_safe == "NONE"
        
        # Test critical condition (score >= 80)
        res_crit = agent.decide_and_act("Zone-A", 85.0, 10.0)
        assert res_crit.startswith("SHUTDOWN_")
        
        # Test critical condition (forecast <= 5)
        res_fast = agent.decide_and_act("Zone-A", 50.0, 3.0)
        assert res_fast.startswith("SHUTDOWN_")
        
    finally:
        if original_key is not None:
            os.environ["GEMINI_API_KEY"] = original_key
        else:
            del os.environ["GEMINI_API_KEY"]


def test_vision_vit_head_forward():
    from utils.local_vision import _model_fire_prob
    
    # Create a synthetic blank image
    img = np.zeros((224, 224, 3), dtype=np.uint8)
    
    # Calling this should run both MLP and ViT (if downloaded) without crashing
    prob_combined, prob_vit = _model_fire_prob(img)
    
    assert isinstance(prob_combined, float)
    assert isinstance(prob_vit, float)
    assert 0.0 <= prob_combined <= 1.0
    assert 0.0 <= prob_vit <= 1.0
