# Sistema de Animação Automatizada para YouTube

Um sistema moderno baseado em agentes de IA para criar animações de alta qualidade a partir de histórias escritas e publicá-las automaticamente no YouTube.

## Visão Geral

Este sistema transforma histórias escritas em animações completas para crianças, automatizando todo o processo de produção de conteúdo para YouTube. O sistema utiliza uma arquitetura de agentes especializados, cada um responsável por uma parte específica do processo de criação.

### Recursos Principais

- **Processamento de Roteiro**: Analisa histórias e as transforma em roteiros estruturados para animação
- **Geração de Imagens**: Cria imagens de alta qualidade para cada cena
- **Animação**: Transforma imagens estáticas em animações fluidas
- **Narração e Áudio**: Gera vozes realistas para narração e diálogos
- **Edição de Vídeo**: Compila todos os elementos em um vídeo final
- **Publicação no YouTube**: Otimiza e faz upload do vídeo para o YouTube

## Arquitetura

O sistema é composto por vários agentes especializados:

1. **Agente de Processamento de Roteiro**: Analisa a história e cria um roteiro estruturado
2. **Agente de Design Visual**: Gera imagens para personagens e cenários
3. **Agente de Animação**: Cria animações para cada cena
4. **Agente de Voz e Áudio**: Gera narração, diálogos e trilha sonora
5. **Agente de Edição**: Compila todos os elementos em um vídeo final
6. **Agente de Publicação**: Otimiza e faz upload do vídeo para o YouTube
7. **Agente Coordenador**: Orquestra o fluxo de trabalho entre todos os agentes

## Requisitos

- Python 3.8+
- Dependências listadas em `requirements.txt`
- Chaves de API para (pelo menos uma das opções de IA generativa):
  - Qwen2.5 (processamento de texto e geração de imagens) - **Recomendado**
  - OpenAI (GPT-4 e DALL-E) - Alternativa
  - ElevenLabs (geração de voz)
  - Stability AI (opcional)
  - Runway (animação)
  - YouTube Data API v3 (publicação)

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/sistema-animacao-youtube.git
cd sistema-animacao-youtube
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:

Crie um arquivo `.env` na raiz do projeto baseado no arquivo `.env.example` fornecido:
```bash
cp .env.example .env
```

Edite o arquivo `.env` e adicione suas chaves de API. Para usar o Qwen2.5 (recomendado):
```

3. Configure as chaves de API:
   - Crie um arquivo `.env` na raiz do projeto
   - Adicione suas chaves de API seguindo o modelo em `.env.example`

## Uso

1. Coloque sua história em um arquivo de texto na pasta `data/`
2. Execute o sistema:
```bash
python main.py --story data/sua_historia.txt
```

3. Os resultados serão salvos na pasta `output/`

## Personalização

Você pode personalizar vários aspectos do sistema editando o arquivo `config/settings.py`:

- Estilo visual das animações
- Vozes dos personagens
- Configurações de vídeo
- Configurações de upload para o YouTube

## Fluxo de Trabalho

1. O usuário fornece uma história em formato de texto
2. O sistema analisa e estrutura a história em cenas
3. Para cada cena:
   - Gera imagens dos personagens e cenários
   - Cria animações
   - Gera áudio para narração e diálogos
4. O sistema compila todas as cenas em um vídeo completo
5. O vídeo é otimizado e enviado para o YouTube

## Tecnologias Utilizadas

- **Processamento de Linguagem Natural**: OpenAI GPT-4
- **Geração de Imagens**: DALL-E, Stable Diffusion
- **Animação**: Runway Gen-2, D-ID
- **Síntese de Voz**: ElevenLabs
- **Edição de Vídeo**: FFmpeg, MoviePy
- **Publicação**: YouTube Data API v3

## Status do Projeto

Este projeto está em desenvolvimento ativo. Atualmente, o Agente de Processamento de Roteiro está implementado e funcional.

## Próximos Passos

- Implementação do Agente de Design Visual
- Implementação do Agente de Animação
- Implementação do Agente de Voz e Áudio
- Implementação do Agente de Edição
- Atualização do Agente de Publicação no YouTube
- Desenvolvimento da interface do usuário

## Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.
