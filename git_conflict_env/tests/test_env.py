import pytest
from models import ReviewAction
from server.git_conflict_environment import GitReviewEnvironment

def test_env_initialization():
    env = GitReviewEnvironment()
    obs = env.reset(task="easy", seed=42)
    assert not obs.done
    assert "utils.py" in obs.current_files
    assert "calculate" in obs.current_files["utils.py"]

def test_env_review_flow():
    env = GitReviewEnvironment()
    env.reset(task="easy", seed=42)
    
    # Post a comment
    obs = env.step(ReviewAction(
        action_type="POST_COMMENT",
        file_path="utils.py",
        line_number=4,
        comment="This is a logic bug! It should be multiplication."
    ))
    assert not obs.done
    assert any("This is a logic bug" in thread for thread in obs.comment_threads)
    
    # Submit patch
    fixed_content = "def calculate_total(items, tax_rate=0.1):\n    subtotal = sum(item[\"price\"] * item[\"quantity\"] for item in items)\n    tax = subtotal * tax_rate\n    total = subtotal + tax\n    return round(total, 2)\n"
    obs = env.step(ReviewAction(
        action_type="SUBMIT_PATCH",
        file_path="utils.py",
        resolved_content=fixed_content
    ))
    assert obs.current_files["utils.py"] == fixed_content
    
    # Run tests
    obs = env.step(ReviewAction(action_type="RUN_TESTS"))
    assert obs.test_results["test_calculate_total"] is True
    
    # Approve
    obs = env.step(ReviewAction(action_type="APPROVE_PR"))
    assert obs.done
    assert obs.reward > 0.5  # Should get a good score for passing tests
