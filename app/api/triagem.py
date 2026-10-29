import logging

from fastapi import APIRouter

from app.agent.provisorio import triar  # trocar pelo agente real depois
from app.models import (
    DecisaoRoteamento,
    Destino,
    DocumentoEntrada,
    DocumentoIngerido,
    RespostaTriagem,
)
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["triagem"])


@router.post("/triagem", response_model=RespostaTriagem)
def triagem(entrada: DocumentoEntrada) -> RespostaTriagem:
    storage = get_storage()

    # 1) Guarda o original assim que chega
    try:
        storage.salvar_recebido(
            entrada.documento_id, entrada.model_dump_json().encode("utf-8"), "json"
        )
    except Exception:
        logger.exception("Falha ao salvar documento recebido")

    # 2) Processa; qualquer falha cai em revisão humana
    doc = DocumentoIngerido(
        documento_id=entrada.documento_id,
        tipo_arquivo=entrada.tipo_arquivo,
        metodo_ingestao="texto_direto",
        texto=entrada.documento_texto,
        canal_origem=entrada.canal_origem,
        erro=None if entrada.documento_texto else "documento_texto ausente",
    )
    try:
        resposta = triar(doc)
    except Exception:
        logger.exception("Falha na triagem")
        resposta = RespostaTriagem(
            status="revisao_humana",
            documento_id=entrada.documento_id,
            decisao_roteamento=DecisaoRoteamento(
                destino_principal=Destino.REVISAO_HUMANA,
                requer_auditoria_humana=True,
                justificativa_roteamento="Falha interna durante a triagem.",
            ),
        )

    # 3) Guarda o resultado e informa o status do backup
    resposta.armazenamento_oci = storage.salvar_resultado(resposta)
    return resposta