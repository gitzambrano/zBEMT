# To-do

1. **Unificar nomenclatura de eixos (Vx, Vz, alpha, mu, J, lambda, etc.) entre GUI, `.bemt`, CLI e engine.**
   Hoje a letra usada para "eixo do escoamento" (x vs z) muda de sentido entre modo rotor e modo hélice (ver CLAUDE.md, seção "Axes convention"), e o motor (`bemt.py`, `FlightCondition`) trabalha sempre em eixos de disco, enquanto GUI/relatório mostram eixos de veículo — isso já gera confusão mesmo estando documentado. Levantar TODOS os pontos onde uma grandeza de eixo aparece com nome diferente do que a GUI mostra: chaves de `FlightCondition`/`BEMTConfig`, campos salvos em `.bemt`, flags do CLI (`cli.py`), rótulos internos de `studies.py`/`api.py` (`_SIMBOLO_DE_COLUNA_HELICE` etc.). Não tocar no `bemt.py` (motor) nem na convenção de eixos de disco internos — só a camada de entrada/saída (`api.py`, `models.py`, `cli.py`, GUI, relatório, `.bemt`) deve passar a usar a nomenclatura da GUI como única fonte da verdade, com uma tabela de tradução centralizada e testada (não espalhada em comentários). Atualizar `docs/software_requirements.md` e o CLAUDE.md de acordo.
   Criar um SVG com a convenção de eixos (rotor: shaft vertical, x edgewise/z axial; hélice: shaft horizontal, x axial/z cross-flow) para deixar visualmente inequívoco qual eixo é qual em cada modo — usar no `documentation.html` e talvez como help popup na GUI.

2. **Refactor total do `documentation.html`.**
   Reescrever para ficar mais claro, conciso e direto (hoje tem texto redundante/prolixo em vários pontos). Conferir cada seção contra o estado atual do código (`api.py`, `bemt.py`, `models.py`, GUI) — provavelmente há trechos que citam campos/fluxos que já mudaram. Já existe `tests/test_documentation.py` cobrindo âncoras, imagens, módulos citados etc.; manter esses testes passando e, se necessário, adicionar novas checagens de consistência durante o refactor.

3. **Adicionar passos temporais: Pitt-Peters dinâmico e stall dinâmico transientes.**
   Hoje o solver resolve estado estacionário/quase-estacionário por caso. Introduzir integração no tempo (mesmo que simples, tipo Euler/RK) do inflow dinâmico (Pitt-Peters com derivadas temporais, não só a forma estática já usada) e do modelo de stall dinâmico (histerese de Cl/Cd em função da taxa de variação de alfa), permitindo simular manobras/transientes e não só pontos de operação isolados.

4. **Adicionar flapping e lead-lag simplificados (rigidez/offset virtual), acoplados ao Pitt-Peters.**
   Modelar o batimento (flapping) e o avanço-atraso (lead-lag) das pás via aproximação de mola/offset virtual (não elasticidade real de pá), acoplado ao inflow dinâmico de Pitt-Peters do item 3, para capturar o efeito desses graus de liberdade na resposta do rotor sem precisar de um modelo aeroelástico completo.

5. **Suporte para XFoil.**
   Permitir gerar/importar polares de perfil via XFoil (hoje há NeuralFoil, ver `external_solvers.py`) como alternativa/complemento, seguindo o mesmo padrão de integração externa já usado (flag no CLI, opção na GUI, mesmo pipeline de tabela de perfil).

6. **Suporte para comparar diferentes geometrias.**
   Permitir carregar/rodar múltiplas geometrias de rotor/hélice lado a lado (mesma condição de voo ou não) e visualizar os resultados sobrepostos/comparados em plots e tabela — hoje o fluxo é sempre um projeto/uma geometria por vez.

7. **Modo de projeto (design mode): varredura fatorial de geometria + plots úteis.**
   Além do fatorial de condições de voo que já existe (`sweep_kind="factorial"` em `studies.py`), permitir fatorial sobre parâmetros de geometria (torção, corda, twist, etc.) para fins de projeto/otimização, com plots comparativos entre as geometrias geradas (ex: FM vs. parâmetro, envelope de desempenho).

8. **Modo de derivadas de estabilidade e controle.**
   Calcular numericamente (perturbação em torno do ponto de trim) as derivadas de estabilidade e controle clássicas (ex: dCT/dmu, dCT/dcolective, derivadas de momento, etc.), incluindo os efeitos de flapping, lead-lag (item 4) e inflow dinâmico (item 3) na resposta — necessário para análise de voo/controle além do desempenho estático já coberto.
