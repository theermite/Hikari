"""Les tests de garde-fous provoquent des refus à la chaîne: aucun ne doit écrire dans le vrai journal de frictions."""

import os

os.environ.setdefault("FRICTION_LOG_OFF", "1")
