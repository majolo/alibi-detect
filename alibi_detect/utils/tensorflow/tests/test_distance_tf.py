import numpy as np
from itertools import product
import pytest
import tensorflow as tf
from alibi_detect.utils.tensorflow import GaussianRBF, mmd2, mmd2_from_kernel_matrix, permed_lsdds
from alibi_detect.utils.tensorflow import relative_euclidean_distance, squared_pairwise_distance

n_features = [2, 5]
n_instances = [(100, 100), (100, 75)]
tests_pairwise = list(product(n_features, n_instances))
n_tests_pairwise = len(tests_pairwise)


@pytest.fixture
def pairwise_params(request):
    return tests_pairwise[request.param]


@pytest.mark.parametrize('pairwise_params', list(range(n_tests_pairwise)), indirect=True)
def test_pairwise(pairwise_params):
    n_features, n_instances = pairwise_params
    xshape, yshape = (n_instances[0], n_features), (n_instances[1], n_features)
    np.random.seed(0)
    x = tf.convert_to_tensor(np.random.random(xshape).astype('float32'))
    y = tf.convert_to_tensor(np.random.random(yshape).astype('float32'))

    dist_xx = squared_pairwise_distance(x, x).numpy()
    dist_xy = squared_pairwise_distance(x, y).numpy()

    assert dist_xx.shape == (xshape[0], xshape[0])
    assert dist_xy.shape == n_instances
    np.testing.assert_almost_equal(dist_xx.trace(), 0., decimal=5)


tests_mmd = tests_pairwise
n_tests_mmd = n_tests_pairwise


@pytest.fixture
def mmd_params(request):
    return tests_mmd[request.param]


@pytest.mark.parametrize('mmd_params', list(range(n_tests_mmd)), indirect=True)
def test_mmd(mmd_params):
    n_features, n_instances = mmd_params
    xshape, yshape = (n_instances[0], n_features), (n_instances[1], n_features)
    np.random.seed(0)
    x = tf.convert_to_tensor(np.random.random(xshape).astype('float32'))
    y = tf.convert_to_tensor(np.random.random(yshape).astype('float32'))
    mmd_xx = mmd2(x, x, kernel=GaussianRBF(sigma=tf.ones(1)))
    mmd_xy = mmd2(x, y, kernel=GaussianRBF(sigma=tf.ones(1)))
    assert mmd_xy > mmd_xx


n = [10, 100]
m = [10, 100]
permute = [True, False]
zero_diag = [True, False]
tests_mmd_from_kernel_matrix = list(product(n, m, permute, zero_diag))
n_tests_mmd_from_kernel_matrix = len(tests_mmd_from_kernel_matrix)


@pytest.fixture
def mmd_from_kernel_matrix_params(request):
    return tests_mmd_from_kernel_matrix[request.param]


@pytest.mark.parametrize('mmd_from_kernel_matrix_params',
                         list(range(n_tests_mmd_from_kernel_matrix)), indirect=True)
def test_mmd_from_kernel_matrix(mmd_from_kernel_matrix_params):
    n, m, permute, zero_diag = mmd_from_kernel_matrix_params
    n_tot = n + m
    shape = (n_tot, n_tot)
    kernel_mat = np.random.uniform(0, 1, size=shape)
    kernel_mat_2 = kernel_mat.copy()
    kernel_mat_2[-m:, :-m] = 1.
    kernel_mat_2[:-m, -m:] = 1.
    kernel_mat = tf.convert_to_tensor(kernel_mat)
    kernel_mat_2 = tf.convert_to_tensor(kernel_mat_2)
    if not zero_diag:
        kernel_mat -= tf.linalg.diag(tf.linalg.diag_part(kernel_mat))
        kernel_mat_2 -= tf.linalg.diag(tf.linalg.diag_part(kernel_mat_2))
    mmd = mmd2_from_kernel_matrix(kernel_mat, m, permute=permute, zero_diag=zero_diag)
    mmd_2 = mmd2_from_kernel_matrix(kernel_mat_2, m, permute=permute, zero_diag=zero_diag)
    if not permute:
        assert mmd_2.numpy() < mmd.numpy()


def test_relative_euclidean_distance():
    x = tf.convert_to_tensor(np.random.rand(5, 3))
    y = tf.convert_to_tensor(np.random.rand(5, 3))

    assert (relative_euclidean_distance(x, y).numpy() == relative_euclidean_distance(y, x).numpy()).all()
    assert (relative_euclidean_distance(x, x).numpy() == relative_euclidean_distance(y, y).numpy()).all()
    assert (relative_euclidean_distance(x, y).numpy() >= 0.).all()


n = [10]
m = [10]
d = [3]
B = [20]
n_kcs = [5]
tests_permed_lsdds = list(product(n, m, d, B, n_kcs))
n_tests_permed_lsdds = len(tests_permed_lsdds)


@pytest.fixture
def permed_lsdds_params(request):
    return tests_permed_lsdds[request.param]


@pytest.mark.parametrize('permed_lsdds_params',
                         list(range(n_tests_permed_lsdds)), indirect=True)
def test_permed_lsdds(permed_lsdds_params):
    n, m, d, B, n_kcs = permed_lsdds_params

    kcs = tf.random.normal((n_kcs, d))
    x_ref = tf.random.normal((n, d))
    x_cur = 10 + 0.2*tf.random.normal((m, d))

    x_full = tf.concat([x_ref, x_cur], axis=0)
    sigma = tf.constant((1.,))
    k_all_c = GaussianRBF(sigma)(x_full, kcs)
    H = GaussianRBF(np.sqrt(2.)*sigma)(kcs, kcs)

    perms = [tf.random.shuffle(tf.range(n+m)) for _ in range(B)]
    x_perms = [perm[:n] for perm in perms]
    y_perms = [perm[n:] for perm in perms]

    lsdd_perms, H_lam_inv, lsdd_unpermed = permed_lsdds(
        k_all_c, x_perms, y_perms, H, return_unpermed=True
    )

    assert int(tf.reduce_sum(tf.cast(lsdd_perms > lsdd_unpermed, float))) == 0
    assert H_lam_inv.shape == (n_kcs, n_kcs)
