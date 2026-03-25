class HealthMonitor:
    def __init__(self):
        pass

    def registrar_uso(self, provider, service):
        # Apenas um placeholder por enquanto
        pass

    def registrar_erro(self, provider, service, error):
        print(f"[HEALTH] Erro em {provider}/{service}: {error}")

_monitor = HealthMonitor()

def get_health_monitor():
    return _monitor
