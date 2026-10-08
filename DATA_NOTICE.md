# Nota sobre os dados

O arquivo `data/acervo.sqlite3` é um índice derivado das planilhas de inventário usadas no projeto. Ele é incluído para permitir que a demonstração pública funcione sem publicar os arquivos XLS originais e seus metadados internos.

A licença MIT deste repositório cobre o código-fonte da aplicação, mas **não concede direitos adicionais sobre o conteúdo arquivístico**. Antes de divulgar o site ou reutilizar os dados em outro contexto, o responsável pelo repositório deve confirmar a procedência, a autorização de publicação e as condições de uso aplicáveis ao acervo.

As planilhas originais são ignoradas pelo Git e devem permanecer sob a guarda de quem mantém o projeto. Para atualizar o índice, coloque-as localmente na pasta `docs`, execute `python3 importer.py` e revise o resultado antes de publicar a nova versão do banco.
