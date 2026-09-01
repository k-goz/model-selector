from verify_ground_truth import model_exists


def test_model_exists_uses_exact_normalized_name_and_platform():
    models = [
        {"platform_id": "moonshot", "name": "moonshot-v1-8k-vision-preview"},
        {"platform_id": "openrouter", "name": "moonshot-v1-8k"},
    ]

    assert not model_exists(models, "moonshot", "moonshot-v1-8k")
    assert model_exists(models, "moonshot", "moonshot_v1_8k_vision_preview")
