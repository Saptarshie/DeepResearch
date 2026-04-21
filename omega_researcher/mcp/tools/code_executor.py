"""Docker sandbox code executor."""
from __future__ import annotations
from omega_researcher.config import Config

ANALYTICS_PREAMBLE = """# Available libraries: pandas, numpy, scipy, sklearn, statsmodels,
# matplotlib, seaborn, plotly, openpyxl, xlrd, tabulate, pyarrow
# Files from the research session are mounted at /data/
"""


class CodeExecutor:
    """Execute Python code in an isolated Docker container."""

    def __init__(self, config: Config):
        self.config = config
        self.image = config.docker_executor_image
        self.timeout = config.docker_executor_timeout
        self._client = None
        self._available = False
        self._init_docker()

    def _init_docker(self):
        try:
            import docker
            self._client = docker.from_env()
            self._client.ping()
            self._available = True
            print("[code_executor] Docker available")
        except Exception as e:
            print(f"[code_executor] Docker not available ({e}) — code execution disabled")

    def run(self, code: str, timeout: int | None = None) -> str:
        """Execute Python code in isolated container. Returns stdout (capped at 5000 chars)."""
        if not self._available or not self._client:
            return "[ERROR] Docker not available. Cannot execute code."

        import tempfile, os
        timeout = timeout or self.timeout
        full_code = ANALYTICS_PREAMBLE + "\n" + code

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(full_code)
                script_path = f.name

            container = self._client.containers.run(
                image=self.image,
                command="python /script/run.py",
                volumes={
                    script_path: {"bind": "/script/run.py", "mode": "ro"},
                    os.getcwd(): {"bind": "/data", "mode": "ro"},
                },
                network=self.config.docker_network,
                mem_limit="512m",
                cpu_quota=50000,
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
            )
            output = container.decode("utf-8") if isinstance(container, bytes) else str(container)
            return output[:5000]

        except Exception as e:
            return f"[code_executor ERROR] {type(e).__name__}: {e}"
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass
