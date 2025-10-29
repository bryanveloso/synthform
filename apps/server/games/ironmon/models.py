from __future__ import annotations

from django.db import models


class Challenge(models.Model):
    """An IronMON challenge (e.g., Kaizo Emerald, Survival)."""

    name = models.TextField(unique=True)

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class Checkpoint(models.Model):
    """A checkpoint within a challenge (gym leader, Elite Four member, Champion)."""

    name = models.TextField(unique=True)
    trainer = models.TextField()
    order = models.IntegerField()
    challenge = models.ForeignKey(
        Challenge, on_delete=models.RESTRICT, related_name="checkpoints"
    )

    class Meta:
        indexes = [
            models.Index(fields=["challenge", "order"]),
            models.Index(fields=["challenge"]),
            models.Index(fields=["order"]),
        ]
        ordering = ["order"]

    def __str__(self):
        return f"{self.challenge.name} - {self.order}. {self.trainer}"


class Seed(models.Model):
    """
    A seed represents one attempt at a challenge.
    IMPORTANT: ID is NOT auto-increment - it comes from the IronMON plugin seed count.
    """

    id = models.IntegerField(primary_key=True)
    challenge = models.ForeignKey(
        Challenge, on_delete=models.RESTRICT, related_name="seeds"
    )

    class Meta:
        indexes = [models.Index(fields=["challenge"])]

    def __str__(self):
        return f"Seed {self.id} - {self.challenge.name}"


class Result(models.Model):
    """Records whether a checkpoint was cleared (True) or failed (False) for a specific seed."""

    seed = models.ForeignKey(Seed, on_delete=models.RESTRICT, related_name="results")
    checkpoint = models.ForeignKey(
        Checkpoint, on_delete=models.RESTRICT, related_name="results"
    )
    result = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seed", "checkpoint"], name="unique_seed_checkpoint"
            )
        ]
        indexes = [
            models.Index(fields=["seed"]),
            models.Index(fields=["checkpoint"]),
            models.Index(fields=["result"]),
        ]

    def __str__(self):
        status = "✅" if self.result else "❌"
        return f"{status} Seed {self.seed_id} - {self.checkpoint.name}"
