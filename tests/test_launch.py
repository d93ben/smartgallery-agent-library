import json
import pytest
from launch import configure


def test_rejects_library_inside_disposable_output(tmp_path):
    comfy = tmp_path / 'ComfyUI'; comfy.mkdir()
    config = tmp_path / 'local.json'
    config.write_text(json.dumps({'comfy_path': str(comfy), 'data_path': str(tmp_path / 'data'),
                                 'library_path': str(comfy / 'output' / 'keepers')}))
    with pytest.raises(ValueError, match='separate'):
        configure(config)
