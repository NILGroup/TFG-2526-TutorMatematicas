# Run dry run
python -m scripts.build_dataset --dataset openai/gsm8k --config socratic --kc-tags-file data/kc_tags.json --taxonomy-file data/taxonomy.in --max-samples 50 --dry-run

# Run phase A only
python -m scripts.build_dataset --dataset openai/gsm8k --config socratic --split train --kc-tags-file data/kc_tags.json --taxonomy-file data/taxonomy.in --phase A --max-samples 50

# Run phase B only
python -m scripts.build_dataset --dataset openai/gsm8k --config socratic --split train --kc-tags-file data/kc_tags.json --taxonomy-file data/taxonomy.in --phase B --max-samples 50

# Run phase C only
python -m scripts.build_dataset --dataset openai/gsm8k --config socratic --split train --kc-tags-file data/kc_tags.json --taxonomy-file data/taxonomy.in --phase C --validate --validation-rate 0.2

# Run all
python -m scripts.build_dataset --dataset openai/gsm8k --config socratic --split train --kc-tags-file data/kc_tags.json --taxonomy-file data/taxonomy.in --max-samples 700 --validate --validation-rate 0.2