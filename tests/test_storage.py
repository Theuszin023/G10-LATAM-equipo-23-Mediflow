import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DecisaoRoteamento, Destino, RespostaTriagem
from app.services.storage import LocalStorage, caminho_resultado, validar_id


def _resposta(destino: Destino, auditoria: bool, doc_id: str = "DOC-1") -> RespostaTriagem:
    return RespostaTriagem(
        status="processado",
        documento_id=doc_id,
        decisao_roteamento=DecisaoRoteamento(
            destino_principal=destino,
            requer_auditoria_humana=auditoria,
            justificativa_roteamento="teste",
        ),
    )


def test_caminho_urgente():
    assert caminho_resultado(_resposta(Destino.EMERGENCIA, False)) == "processados/urgentes/DOC-1.json"


def test_caminho_rotina():
    assert caminho_resultado(_resposta(Destino.PRONTUARIO, False)) == "processados/rotina/DOC-1.json"


def test_caminho_auditoria():
    assert caminho_resultado(_resposta(Destino.REVISAO_HUMANA, True)) == "auditoria_humana/DOC-1.json"


@pytest.mark.parametrize("ruim", ["../x", "a/b", "..", "", "a b"])
def test_id_invalido_e_rejeitado(ruim):
    with pytest.raises(ValueError):
        validar_id(ruim)


def test_salvar_resultado_grava_arquivo(tmp_path):
    storage = LocalStorage(str(tmp_path), "bucket-teste")
    arm = storage.salvar_resultado(_resposta(Destino.PRONTUARIO, False))
    assert arm.status_backup == "sucesso"
    assert (tmp_path / "processados" / "rotina" / "DOC-1.json").exists()


def test_id_malicioso_nao_grava_e_marca_falha(tmp_path):
    storage = LocalStorage(str(tmp_path), "bucket-teste")
    arm = storage.salvar_resultado(_resposta(Destino.PRONTUARIO, False, doc_id="../fora"))
    assert arm.status_backup == "falha"


def test_endpoint_retorna_caminho_no_storage():
    client = TestClient(app)
    r = client.post(
        "/triagem",
        json={
            "documento_id": "DOC-URG-1",
            "tipo_arquivo": "PDF",
            "documento_texto": "Laudo de tomografia. Conclusao: TEP agudo. Sugere-se correlacao clinica urgente.",
            "canal_origem": "Pronto_Socorro",
        },
    )
    arm = r.json()["armazenamento_oci"]
    assert arm["status_backup"] == "sucesso"
    assert arm["caminho_objeto"] == "processados/urgentes/DOC-URG-1.json"