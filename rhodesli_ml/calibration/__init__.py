"""Learned similarity calibration on frozen InsightFace embeddings.

Trains a Siamese MLP on confirmed identity pairs to output calibrated
match probabilities. See PRD-023 and SDD-023 for design details.

Decision provenance: AD-123, AD-124, AD-125.
"""
