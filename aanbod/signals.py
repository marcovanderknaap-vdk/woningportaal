from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Makelaar, Woning


@receiver(post_delete, sender=Woning)
def foto_weg_met_woning(sender, instance, **kwargs):
    """Een verwijderde woning neemt zijn foto mee, zodat er geen losse bestanden achterblijven."""
    if instance.foto:
        instance.foto.delete(save=False)


@receiver(post_delete, sender=Makelaar)
def logo_weg_met_makelaar(sender, instance, **kwargs):
    if instance.logo:
        instance.logo.delete(save=False)
