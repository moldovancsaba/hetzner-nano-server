"""Tests that gateway.server.Runner passes an explicit non-thinking profile ('think' False) to image
recognition and moderation, and leaves the request unchanged when the profile has no such control."""
import json,unittest
from unittest.mock import Mock,patch
from gateway.server import Runner

class VisionProfileTests(unittest.TestCase):
    def test_recognition_passes_explicit_nonthinking_profile(self):
        catalog=Mock();catalog.profile.return_value={'max_image_edge':640,'think':False}
        runner=Runner(catalog);runner.switch=Mock(return_value={})
        data={'done':True,'done_reason':'stop','response':json.dumps({'description':'Birds.','objects':['bird'],'visible_text':[]})}
        with patch('gateway.server.native',return_value=data) as native:
            runner('image_recognition',b'test-image','candidate')
        self.assertIs(native.call_args.args[1]['think'],False)
    def test_ordinary_vision_profile_keeps_existing_request(self):
        catalog=Mock();catalog.profile.return_value={'max_image_edge':640}
        runner=Runner(catalog);runner.switch=Mock(return_value={})
        data={'done':True,'done_reason':'stop','response':json.dumps({'description':'Birds.','objects':['bird'],'visible_text':[]})}
        with patch('gateway.server.native',return_value=data) as native:
            runner('image_recognition',b'test-image','candidate')
        self.assertNotIn('think',native.call_args.args[1])
    def test_moderation_receives_same_profile_control(self):
        catalog=Mock();catalog.profile.return_value={'max_image_edge':640,'think':False}
        runner=Runner(catalog);runner.switch=Mock(return_value={})
        with patch('gateway.server.moderation_infer',return_value={'review_required':True}) as infer:
            runner('image_moderation',b'test-image','candidate')
        infer.assert_called_once_with(b'test-image',model='candidate',think=False)

if __name__=='__main__':unittest.main()
