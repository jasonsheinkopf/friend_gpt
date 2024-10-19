# <img src="media/friend.jpeg" alt="Your GIF" width="25"> Friend GPT 
Friend GPT is an customizable LLM agent with memory that can interact through Discord private chats and servers. It can be
served by API to closed-source models or locally through Ollama.

# Novel Response Method
To simulate a more human interaction, the agent does note respond once per prompt. Instead

# Short Term Memory
Chat messages are stored in a SQLite db chat_history table. User can customize the length of the tail to be included in the prompt to the agent.
<img src="media/chat_history.jpeg" alt="Your GIF" width="800">

# Long Term Memory
The model regularly checks if the length of short term memory is past a threshold. If so, the undigested history is summarized with
an additional LLM call, embedded into vector space by SentenceTransformers, and added to a FAISS vector index. Each text chunk is then added to a
different chat_vector_memory table in the db along with its retrivel index. Each agent prompt includes results from the top 3 most relevant
chunks retrieved by vector similarity.

# Models
All models are run using Ollama on a Mac M2 32GB. Models are Gemma2:9b, Llama3.1:8b. Each debate either used instances of the same model 
or an even mixture of both. In instances where the number of agents did not divide evenly by the number of models, the model majority
type was chosen at random.

# Datasets
## Arithmetic
Using a seed, I randomly generated arithmetic problems with 6 integers chosen from a range of [20, 100].
This range was arrived at by experimentation and surely differs from the original experiment. I found that integer
ranges that were too low created expressions that were too easily solved. Operators were randomly selected from +, *, and -.
## GSM8K
This dataset provides grade school math word problems, which had a numeric answer.

# Prompts
For the first round, each model was provided the hand-written prompt, which guided the model to respond with
its work shown as well as a final answer that could be reliably extracted.

 ```
What is the result of {question}? Please follow these instructions carefully:


   1. Show your work step-by-step.
   2. Ensure your final answer is clearly stated on a new line.
   3. The final answer must be enclosed in angle brackets, like this: <5>.
   4. Do not add any extra characters, spaces, or text inside the brackets.


   For example:
   Step-by-step solution here...
   Final answer on its own line:
   <5>


   Remember, the final answer should always be on its own line, and enclosed in <>.
```
On each subsequent round, each model received an additional prompt, followed by responses of all agents (including their own)
from the previous round. Agents were not given any information that would let them associate a response with its agent’s identity.

```
Consider the following responses to the same question from other agents. If you think they are correct, you can use them to help
you answer the question. If you think they are incorrect, you can ignore them.
```

`Imagine you are a {persona}. Use your expertise and study in crafting your answer.`

# Personas

For the persona experiments, at the beginning of each new question, the list of personas was shuffled and dealt out without
replacement to the agents. Agent personas persisted throughout each question.

These personas included 'doctor', 'lawyer', 'teacher', 'engineer', 'scientist'

# Logic
At the end of each round, the responses were parsed to isolate the final response. If all models were in agreement, then
the debate ended. Results were written to a json file with each debate being provided with a unique hash.

# Results
Due to the variety of experiments and time constraints, each experiment category was only run for 50 questions of each type. 

## Arithmetic
Without providing personas, Gemma and Llama both showed increased accuracy with more agents in the debate.
However, combining the models showed the opposite trend. Adding personas to the models interestingly achieve similarly
uplifting results even for the baseline individual agent.

<img src="results/visualizations/arithmetic_bar.png" alt="Your GIF" width="800">
<img src="results/visualizations/arithmetic_results.png" alt="Your GIF" width="800">

## GSM8K
For this dataset, an increase in number of agents was noticeable but not as prominent for Gemma. However, Llama experienced
a decrease in accuracy. Gemma showed benefits from the persona prompt, while Llama also showed a decrease. Despite the
difference in effectiveness between the models, the experiment with the greatest accuracy also had the greatest variety,
using both models, different personas, and the maximum number of agents.

<img src="results/visualizations/gsm8k_bar.png" alt="Your GIF" width="800">
<img src="results/visualizations/gsm8k_results.png" alt="Your GIF" width="800">

# Instructions

## Create virtual environment
requirements.txt

## Run LLMs locally with Ollama
* install [Ollama](https://ollama.com/)
* `ollama run llama3.1:8b`
* `ollama run gemma2:9b`

## View Existing Results
* open `visualize_results.ipynb`
* run all

## Test on More Samples of Provided Dataset Benchmarks
* choose or modify an experiment yaml file, such as `configs/arithmetic_persona.yaml`
* in terminal, run `main.py --cfg configs/arithmetic_persona.yaml
* command line arguments can be added `main.py --cfg configs/arithmetic_persona.yaml DEB_PER_EXP 50 MAX_AGENTS 5`
* questions already solved will be skipped
* each question is solved by all experiment permutations before advancing to a new question
