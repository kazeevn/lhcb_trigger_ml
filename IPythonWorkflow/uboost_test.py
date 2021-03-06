#!/usr/bin/env python

import pylab as pl
import numpy as np
from itertools import izip
import argparse
from sklearn.metrics.metrics import roc_auc_score, accuracy_score
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble.weight_boosting import AdaBoostClassifier

from commonutils import generate_sample
from supplementaryclassifiers import HidingClassifier
from uboost import uBoostBDT, uBoostClassifier
from reports import Predictions, ClassifiersDict


def test_cuts(n_samples=1000):
    base_classifier = DecisionTreeClassifier(min_samples_leaf=10, max_depth=6)
    trainX, trainY = generate_sample(n_samples, 10, 0.6)
    uniform_variables = ['column0']

    for algorithm in ['SAMME', 'SAMME.R']:
        for target_efficiency in [0.1, 0.3, 0.5, 0.7, 0.9]:
            uBDT = uBoostBDT(
                uniform_variables=uniform_variables,
                target_efficiency=target_efficiency,
                n_neighbors=20, n_estimators=20,
                algorithm=algorithm,
                base_estimator=base_classifier)
            uBDT.fit(trainX, trainY)

            passed = sum(trainY) * target_efficiency

            assert uBDT.score_cut == uBDT.score_cuts_[-1],\
                'something wrong with computed cuts'

            for score, cut in izip(uBDT.staged_predict_score(trainX[trainY > 0.5]),
                                   uBDT.score_cuts_):
                passed_upper = np.sum(score > cut - 1e-7)
                passed_lower = np.sum(score > cut + 1e-7)
                assert passed_lower <= passed <= passed_upper, "wrong stage cuts"


def test_probas(n_samples=1000):
    trainX, trainY = generate_sample(n_samples, 10, 0.6)
    testX, testY = generate_sample(n_samples, 10, 0.6)

    params = {
        'n_neighbors': 10,
        'n_estimators': 10,
        'uniform_variables': ['column0'],
        'base_estimator': DecisionTreeClassifier(max_depth=5)
    }

    for algorithm in ['SAMME', 'SAMME.R']:
        uboost_classifier = uBoostClassifier(
            algorithm=algorithm,
            efficiency_steps=3, **params)

        bdt_classifier = uBoostBDT(algorithm=algorithm, **params)

        for classifier in [bdt_classifier, uboost_classifier]:
            classifier.fit(trainX, trainY)
            proba1 = classifier.predict_proba(testX)
            proba2 = list(classifier.staged_predict_proba(testX))[-1]
            assert np.allclose(proba1, proba2, atol=0.001),\
                "staged_predict doesn't coincide with the predict for proba."

        score1 = bdt_classifier.predict_score(testX)
        score2 = list(bdt_classifier.staged_predict_score(testX))[-1]
        assert np.allclose(score1, score2),\
            "staged_score doesn't coincide with the score."

        assert len(bdt_classifier.feature_importances_) == trainX.shape[1]


def test_quality(n_samples=3000):
    testX, testY = generate_sample(n_samples, 10, 0.6)
    trainX, trainY = generate_sample(n_samples, 10, 0.6)

    params = {
        'n_neighbors': 10,
        'n_estimators': 10,
        'uniform_variables': ['column0'],
        'base_estimator':
            DecisionTreeClassifier(min_samples_leaf=20, max_depth=5)
    }

    for algorithm in ['SAMME', 'SAMME.R']:
        uboost_classifier = uBoostClassifier(
            algorithm=algorithm, efficiency_steps=5, **params)

        bdt_classifier = uBoostBDT(algorithm=algorithm, **params)

        for classifier in [bdt_classifier, uboost_classifier]:
            classifier.fit(trainX, trainY)
            predict_proba = classifier.predict_proba(testX)
            predict = classifier.predict(testX)
            assert roc_auc_score(testY, predict_proba[:, 1]) > 0.7, \
                "quality is awful"
            print("Accuracy = %.3f" % accuracy_score(testY, predict))


def test_classifiers(n_samples=10000, output_name_pattern=None):
    testX, testY = generate_sample(n_samples, 10, 0.6)
    trainX, trainY = generate_sample(n_samples, 10, 0.6)
    uniform_variables = ['column0']

    clf_Ada = AdaBoostClassifier(n_estimators=50)
    clf_NB = HidingClassifier(train_variables=trainX.columns[1:],
                               base_estimator=GaussianNB())
    clf_uBoost_SAMME = uBoostClassifier(
        uniform_variables=uniform_variables,
        n_neighbors=50,
        efficiency_steps=5,
        n_estimators=50,
        algorithm="SAMME")
    clf_uBoost_SAMME_R = uBoostClassifier(
        uniform_variables=uniform_variables,
        n_neighbors=50,
        efficiency_steps=5,
        n_estimators=50,
        algorithm="SAMME.R")
    clf_dict = ClassifiersDict({
        "Ada": clf_Ada,
        "Ideal": clf_NB,
        "uBOOST": clf_uBoost_SAMME,
        "uBOOST.R": clf_uBoost_SAMME_R
        })
    clf_dict.fit(trainX, trainY)

    predictions = Predictions(clf_dict, testX, testY)
    predictions.print_mse(uniform_variables, in_html=False)
    print(predictions.compute_metrics())

    # TODO(kazeevn)
    # Make reports save the plots.

    predictions.mse_curves(uniform_variables)
    if output_name_pattern is not None:
        pl.savefig(output_name_pattern % "mse_curves", bbox="tight")
    figure1 = pl.figure()
    predictions.learning_curves()
    if output_name_pattern is not None:
        pl.savefig(output_name_pattern % "learning_curves", bbox="tight")
    predictions.efficiency(uniform_variables)
    if output_name_pattern is not None:
        pl.savefig(output_name_pattern % "efficiency_curves", bbox="tight")


def main():
    parser = argparse.ArgumentParser(
        description="Run some assert-based tests, "
        "calculate MSE and plot local efficiencies for"
        " AdaBoost, uBoost.SAMME and uBoost.SAMME.R")
    parser.add_argument('-o', '--output-file', type=str,
                        help=r"Filename pattern with one %%s to save "
                        "the plots to. Example: classifiers_%%s.pdf")
    parser.add_argument('-s', '--random-seed', type=int,
                        help="Random generator seed to use.")
    args = parser.parse_args()
    if args.random_seed:
        np.random.seed(args.random_seed)
    else:
        np.random.seed(42)

    test_cuts()
    test_probas()
    test_quality()
    test_classifiers(10000, args.output_file)

    if args.output_file is None:
        pl.show()

if __name__ == '__main__':
    main()
