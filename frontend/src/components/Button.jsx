// frontend/src/components/Button.jsx
export const Button = ({ variant = "primary", children, ...props }) => {
  return (
    <button className={`btn btn-${variant}`} {...props}>
      {children}
    </button>
  );
};

// frontend/src/components/Card.jsx
export const Card = ({ children, ...props }) => {
  return (
    <article style={{
      padding: 'var(--space-6)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-base)',
      backgroundColor: 'var(--color-white)',
      marginBottom: 'var(--space-6)'
    }} {...props}>
      {children}
    </article>
  );
};
