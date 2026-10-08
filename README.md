# Consulta ao inventário do APBH

Aplicação web para pesquisar um índice derivado de planilhas `.xls` de inventário. Os arquivos originais não são alterados: o importador cria um banco SQLite com pesquisa textual tolerante a acentos, filtros por coleção e período e acesso aos campos originais de cada linha.

## Como executar

Requisitos: Python 3 e `xls2csv` (fornecido pelo pacote `catdoc`).

```bash
./iniciar.sh
```

Depois, abra <http://127.0.0.1:8000> no navegador.

O servidor cria o índice automaticamente na primeira execução. Sempre que as planilhas forem modificadas ou adicionadas, execute `python3 importer.py` e reinicie o servidor.

## Publicação gratuita

O repositório está preparado para publicação no Render usando o arquivo `render.yaml`:

1. Crie um repositório público no GitHub e envie estes arquivos.
2. No Render, escolha **New > Blueprint** e conecte o repositório.
3. Confirme o plano gratuito e aguarde a implantação.

Para configurar o serviço manualmente, use:

- Build Command: `python3 -m pip install -r requirements.txt && python3 -m unittest discover -s tests -v`
- Start Command: `python3 server.py`
- Health Check Path: `/api/health`

O serviço recebe a porta do ambiente automaticamente e oferece `/api/health` para a verificação de disponibilidade. Na modalidade gratuita, o Render pode suspender o serviço após um período sem acessos; a primeira visita seguinte pode demorar cerca de um minuto.

As planilhas em `docs` não são enviadas ao GitHub. A demonstração usa apenas `data/acervo.sqlite3`. Consulte [DATA_NOTICE.md](DATA_NOTICE.md) antes de tornar o repositório público.

## Endpoints

- `GET /api/stats`: totais, coleções e intervalo de anos.
- `GET /api/health`: verificação de disponibilidade do serviço.
- `GET /api/search?q=&collection=&year_from=&year_to=&page=`: pesquisa paginada.
- `GET /api/records/{id}`: ficha completa, incluindo os campos originais.

## Testes

```bash
python3 -m unittest discover -s tests -v
```
