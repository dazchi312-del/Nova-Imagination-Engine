
def count_words(text):
    words = text.split()
    return len(words)

sample = "Nova Imagination Engine is a creative AI built for makers"
count = count_words(sample)
print(f"Word count: {count}")
print(f"Words: {sample.split()}")
