from openhands_aci.code_search import initialize_code_search, search_code


def main():
    # Initialize search for the openhands-aci repo
    print('Initializing code search...')
    result = initialize_code_search(
        repo_path='/workspace/openhands-aci',
        save_dir='/workspace/openhands-aci/code_search_index',
        extensions=['.py'],  # only index Python files
        embedding_model='BAAI/bge-base-en-v1.5',
    )
    print('Initialization result:', result)

    if result['status'] == 'success':
        # Try some searches
        queries = [
            'code that handles file editing',
            'function for running bash commands',
            'code related to linting or code analysis',
        ]

        print('\nTesting searches:')
        for query in queries:
            print(f'\nQuery: {query}')
            result = search_code(
                save_dir='/workspace/openhands-aci/code_search_index', query=query, k=3
            )
            if result['status'] == 'success':
                for doc in result['results']:
                    print(f"\nFile: {doc['path']}")
                    print(f"Score: {doc['score']:.3f}")
                    print('Content preview:', doc['content'][:200] + '...')
            else:
                print('Search failed:', result['message'])


if __name__ == '__main__':
    main()
