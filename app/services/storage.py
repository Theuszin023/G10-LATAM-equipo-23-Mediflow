import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings
from app.models import ArmazenamentoOCI, Destino, RespostaTriagem

logger = logging.getLogger(__name__)

_ID_VALIDO = re.compile(r"[A-Za-z0-9._-]{1,100}")
_EXTENSOES = {"json", "txt", "pdf", "png", "jpg", "jpeg"}


def validar_id(documento_id: str) -> str:
    """Impede ids como '../../x' (path traversal) nos nomes de objeto."""
    if not _ID_VALIDO.fullmatch(documento_id) or ".." in documento_id:
        raise ValueError("documento_id inválido")
    return documento_id


def caminho_resultado(resposta: RespostaTriagem) -> str:
    doc_id = validar_id(resposta.documento_id)
    decisao = resposta.decisao_roteamento
    if decisao is None or decisao.requer_auditoria_humana:
        pasta = "auditoria_humana"
    elif decisao.destino_principal == Destino.EMERGENCIA:
        pasta = "processados/urgentes"
    else:
        pasta = "processados/rotina"
    return f"{pasta}/{doc_id}.json"


class Storage(ABC):
    bucket: str

    @abstractmethod
    def salvar_objeto(self, caminho: str, conteudo: bytes, content_type: str) -> None:
        ...

    def salvar_recebido(self, documento_id: str, conteudo: bytes, extensao: str) -> str:
        doc_id = validar_id(documento_id)
        if extensao not in _EXTENSOES:
            raise ValueError("extensão não permitida")
        caminho = f"recebidos/{doc_id}.{extensao}"
        self.salvar_objeto(caminho, conteudo, "application/octet-stream")
        return caminho

    def salvar_resultado(self, resposta: RespostaTriagem) -> ArmazenamentoOCI:
        try:
            caminho = caminho_resultado(resposta)
            armazenamento = ArmazenamentoOCI(
                bucket=self.bucket, caminho_objeto=caminho, status_backup="sucesso"
            )
            completa = resposta.model_copy(update={"armazenamento_oci": armazenamento})
            self.salvar_objeto(
                caminho,
                completa.model_dump_json(indent=2).encode("utf-8"),
                "application/json",
            )
            return armazenamento
        except Exception:
            logger.exception("Falha ao salvar resultado")
            return ArmazenamentoOCI(
                bucket=self.bucket, caminho_objeto="", status_backup="falha"
            )


class LocalStorage(Storage):
    """Grava em disco, simulando o bucket. Útil enquanto o OCI não está pronto."""

    def __init__(self, raiz: str, bucket: str):
        self.raiz = Path(raiz).resolve()
        self.bucket = bucket

    def salvar_objeto(self, caminho: str, conteudo: bytes, content_type: str) -> None:
        destino = (self.raiz / caminho).resolve()
        if self.raiz not in destino.parents:
            raise ValueError("caminho fora da raiz de armazenamento")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)


def get_storage() -> Storage:
    # Quando o OCI estiver configurado, retornar OciStorage aqui (próximo passo).
    return LocalStorage(settings.local_storage_dir, settings.oci_bucket)