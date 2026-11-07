# Backend do Logbuster com Python

* Principais frameworks e pacotes:
   * [FastAPI](https://fastapi.tiangolo.com/)
   * [SQLAlchemy](https://www.sqlalchemy.org/) (banco de dados [PostgreSQL](https://www.postgresql.org/)).

## Configurando o ambiente

### Instale as ferramentas necessárias

Usamos o `mise` (https://mise.jdx.dev/) para gerenciar o ambiente de desenvolvimento.
Para configurar o ambiente, instale o `mise` seguindo as instruções da sua [documentação](https://mise.jdx.dev/getting-started.html).

Para acessar o banco de dados do projeto, é necessário ter as credenciais e o acesso à rede configurados. Veja as instruções detalhadas em [SETUP_LINK](<!-- TODO: adicionar link -->).

Com o `mise` instalado, use seu terminal preferido (recomendamos o Git Bash no Windows) para entrar com `cd` na pasta raiz deste repositório. Em seguida, execute:

```
mise setup
```

Pronto. Não é preciso instalar Python nem outras dependências, o `mise` cuida de tudo.

### Defina as variáveis de ambiente

Crie um arquivo `.env` com as variáveis de ambiente necessárias (veja o [.env.example](<!-- TODO: adicionar link para o .env.example -->)).

### Execute o servidor

Certifique-se de que o `.env` siga a mesma estrutura do `.env.example`. Copiar o arquivo de exemplo deve bastar. Na pasta raiz do repositório, execute:

```
mise start
```

## O que acontece por baixo dos panos com o `mise`

O `mise` instala as ferramentas necessárias para configurar o ambiente, como a versão adequada do Python e o seu gerenciador de pacotes (usamos o `uv`).

Com o `mise` instalado, ficam disponíveis as tarefas definidas no `mise.toml`, úteis para operações frequentes, como rodar o servidor (`mise start`) ou executar os testes (`mise test`).
Sinta-se à vontade para adicionar novas tarefas úteis ao contexto do repositório.

Embora o `mise` forneça tarefas e instale ferramentas, a execução do código é feita com Python e `uv`. Na pasta raiz, ao executar comandos `uv`, as versões corretas de Python e `uv` são usadas automaticamente, graças ao `mise`.

## Documentação

Com o servidor em execução, é possível acessar a [documentação da API](http://localhost:<PORT>/<!-- TODO: caminho da documentação -->).