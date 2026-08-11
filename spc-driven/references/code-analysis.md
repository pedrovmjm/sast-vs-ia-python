# Ferramentas de análise de código

Use degradação graciosa para pesquisa de código e análise estrutural.

## Prioridade da ferramenta

1. **ast-grep** (`sg`) - Pesquisa baseada em padrões estruturais
2. **ripgrep** (`rg`) - Pesquisa rápida de texto com reconhecimento de contexto
3. **grep** – Pesquisa de texto padrão (sempre disponível)

## Detecção

Verifique a disponibilidade da ferramenta antes de usar:

```bash
# Check for ast-grep
if command -v sg >/dev/null 2>&1; then
  # Use ast-grep for structural search
elif command -v rg >/dev/null 2>&1; then
  # Fall back to ripgrep
else
  # Use standard grep as final fallback
fi
```

## Exemplos de uso

**Encontrando definições de função:**

```bash
# ast-grep (best - structural)
sg -p 'function $NAME($$$) { $$$ }'

# ripgrep (fallback - fast text)
rg '^function\s+\w+\(' --type-add 'source:*.[extension]' -t source

# grep (last resort - basic)
grep -r '^function ' --include="*.[extension]"
```

**Encontrar importações/requer:**

```bash
# ast-grep
sg -p 'import { $$$ } from "$MODULE"'

# ripgrep
rg '^import .* from' --type-add 'source:*.[extension]' -t source

# grep
grep -r '^import ' --include="*.[extension]"
```

**Encontrando definições de classe/componente:**

```bash
# ast-grep
sg -p 'class $NAME { $$$ }'

# ripgrep
rg '^(class|export class)\s+\w+' --type-add 'source:*.[extension]' -t source

# grep
grep -r '^class ' --include="*.[extension]"
```

## Escopo da pesquisa

**Práticas recomendadas:**

- Limite às extensões de arquivo de origem relevantes para o projeto
- Excluir diretórios: `node_modules`, `vendor`, `dist`, `build`, `.git`
- Concentre-se nos diretórios de origem: `src`, `lib`, `app`
- Use filtros de tipo de arquivo quando disponíveis

**Dicas de desempenho:**

- Use padrões específicos em pesquisas amplas
- Limite a profundidade do diretório com `--max-depth` (ripgrep/grep)
- Resultados em cache para consultas repetidas

## Aviso de substituição

Se ast-grep não estiver disponível, exiba uma vez por sessão:

```
⚠️ ast-grep not detected. Install for more precise structural code analysis.
   https://ast-grep.github.io/guide/quick-start.html
```

## Quando usar

- Encontrar padrões de uso na base de código
- Identificação da estrutura e organização do código
- Localizando definições de função/classe/componente
- Analisando padrões de importação/dependência
- Refatoração de análise de impacto
- Navegação de código em bases de código desconhecidas