from .week1 import Week1Module
from .week2 import Week2Module
from .week3 import Week3Module
from .week4 import Week4Module
from .week5 import Week5Module
from .week6 import Week6Module
from .week7 import Week7Module
from .week8 import Week8Module
from .week9 import Week9Module
from .week10 import Week10Module
from .week11 import Week11Module
from .week12 import Week12Module
from .week13 import Week13Module
from .week14 import Week14Module


class WeekRegistry:
    def __init__(self):
        self._modules = {}

    def register(self, module):
        if module.week_number in self._modules:
            raise ValueError(f'Week {module.week_number} is already registered.')
        self._modules[module.week_number] = module

    def get(self, week_number):
        try:
            return self._modules[week_number]
        except KeyError as exc:
            raise KeyError(f'No WeekModule registered for week {week_number}.') from exc

    def all(self):
        return dict(self._modules)


registry = WeekRegistry()
registry.register(Week1Module())
registry.register(Week2Module())
registry.register(Week3Module())
registry.register(Week4Module())
registry.register(Week5Module())
registry.register(Week6Module())
registry.register(Week7Module())
registry.register(Week8Module())
registry.register(Week9Module())
registry.register(Week10Module())
registry.register(Week11Module())
registry.register(Week12Module())
registry.register(Week13Module())
registry.register(Week14Module())
