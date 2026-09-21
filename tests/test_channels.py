import unittest
from fund_atlas.channels import classify_channel


class Channels(unittest.TestCase):
    def test_share_class_and_subscription_status(self):
        samples = [
            ('513100', '纳指ETF国泰', True, 'exchange'),
            ('159696', '纳指ETF易方达', True, 'exchange'),
            ('008971', '大成纳斯达克100ETF联接(QDII)C', False, 'otc'),
            ('161128', '易方达标普信息科技指数(QDII-LOF)A', True, 'both'),
            ('012868', '易方达标普信息科技指数(QDII-LOF)C', False, 'otc'),
            ('501225', '景顺长城全球半导体(QDII-LOF)', True, 'both'),
            ('160000', '未知上市份额', True, 'unknown'),
        ]
        for code, name, listed, expected in samples:
            for status in ['暂停申购', '开放申购', '限大额']:
                with self.subTest(code=code, status=status):
                    self.assertEqual(classify_channel(dict(code=code, name=name, listed=listed, purchase_status=status)), expected)
