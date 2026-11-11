from datetime import date

import pytest

from scripts.publish_ready_articles import eligible_paths


def test_ready_post_and_public_image_are_accepted(tmp_path):
    post = tmp_path / 'docs/journal/2026-11-11-example.md'
    image = tmp_path / 'docs/assets/images/example/figure.svg'
    post.parent.mkdir(parents=True)
    image.parent.mkdir(parents=True)
    post.write_text('# Example\n')
    image.write_text('<svg/>')
    paths = ['docs/journal/2026-11-11-example.md', 'docs/assets/images/example/figure.svg']
    assert eligible_paths(paths, root=tmp_path, today=date(2026, 11, 11)) == paths


@pytest.mark.parametrize('relative', [
    'docs/journal/index.md',
    'docs/journal/2026-11-12-future.md',
    'docs/assets/images/../secret.png',
    '.env',
])
def test_unready_or_out_of_scope_paths_are_rejected(tmp_path, relative):
    valid = tmp_path / 'docs/journal/2026-11-11-example.md'
    valid.parent.mkdir(parents=True)
    valid.write_text('# Example\n')
    with pytest.raises(ValueError):
        eligible_paths(['docs/journal/2026-11-11-example.md', relative],
                       root=tmp_path, today=date(2026, 11, 11))


def test_symlinked_post_is_rejected(tmp_path):
    outside = tmp_path / 'outside.md'
    outside.write_text('# Outside\n')
    post = tmp_path / 'docs/journal/2026-11-11-linked.md'
    post.parent.mkdir(parents=True)
    post.symlink_to(outside)
    with pytest.raises(ValueError):
        eligible_paths(['docs/journal/2026-11-11-linked.md'], root=tmp_path,
                       today=date(2026, 11, 11))
