"""Pure prompt/config tests: no provider or database access."""
from unittest.mock import patch
import pytest
from app.core import owner_generation_config as config
from app.models.photography_plan import PhotographyPlan
from app.schemas.owner_ai import OwnerGenerationPreferences
from app.services import generation_planning as planning


@pytest.mark.parametrize('size', [2, 8])
def test_locations_are_distinct_and_independent_of_pose(size):
    plan = PhotographyPlan(photography_type='Portrait', people_count=1,
        environment='Outdoor', location='Garden', preferences={})
    preferences = OwnerGenerationPreferences().model_dump()
    preferences.update(background_mode='different', outfit_mode='same')
    with patch.object(planning, 'BATCH_SIZE', size):
        shots = planning.planned_owner_shots(plan, preferences)
        assert len(shots) == size
        backgrounds = [shot['instructions'].split('Use ', 1)[1].split(' Keep the same outfit')[0] for shot in shots]
        assert len(set(backgrounds)) == size
        for shot in shots:
            assert 'different physical location' in shot['instructions']
            assert 'same outfit' in shot['instructions']
            assert 'identity, face, hairstyle' in shot['instructions']
        for mode in ['same', 'custom']:
            other = planning.planned_owner_shots(plan, {**preferences, 'background_mode': mode})
            assert [s['pose_name'] for s in other] == [s['pose_name'] for s in shots]
            assert [s['camera_angle'] for s in other] == [s['camera_angle'] for s in shots]
            assert all('different physical location' not in s['instructions'] for s in other)
            assert all(('background and location consistent' if mode == 'same' else 'custom background direction') in s['instructions'] for s in other)
        high = planning.planned_owner_shots(plan, {**preferences, 'pose_mode': 'high'})
        assert all(background in shot['instructions'] for background, shot in zip(backgrounds, high))
        assert len(planning.planned_shots(plan)) == 4


def test_default_and_supported_configuration():
    with patch.object(config.Path, 'exists', return_value=False):
        assert config.load_batch_size() == 8
    for size in (2, 8):
        with patch.object(config.Path, 'read_text', return_value='{"studioOwnerBatchSize": %s}' % size):
            assert config.load_batch_size() == size
    with patch.object(config.Path, 'read_text', return_value='{"studioOwnerBatchSize": 4}'):
        with pytest.raises(ValueError):
            config.load_batch_size()
